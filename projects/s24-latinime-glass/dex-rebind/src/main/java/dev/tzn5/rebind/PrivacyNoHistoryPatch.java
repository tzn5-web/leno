package dev.tzn5.rebind;

import java.io.File;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Set;

import org.jf.dexlib2.DexFileFactory;
import org.jf.dexlib2.Opcode;
import org.jf.dexlib2.iface.ClassDef;
import org.jf.dexlib2.iface.DexFile;
import org.jf.dexlib2.iface.Method;
import org.jf.dexlib2.iface.MethodImplementation;
import org.jf.dexlib2.iface.instruction.Instruction;
import org.jf.dexlib2.immutable.ImmutableMethod;
import org.jf.dexlib2.immutable.ImmutableMethodImplementation;
import org.jf.dexlib2.immutable.instruction.ImmutableInstruction10x;
import org.jf.dexlib2.rewriter.DexRewriter;
import org.jf.dexlib2.rewriter.MethodRewriter;
import org.jf.dexlib2.rewriter.Rewriter;
import org.jf.dexlib2.rewriter.RewriterModule;
import org.jf.dexlib2.rewriter.Rewriters;
import org.jf.dexlib2.writer.pool.DexPool;

/**
 * Suppress identified LatinIME Java entry points that append typed words,
 * update user-history dictionaries or flush dynamic vocabulary to disk.
 * Preserve the built-in read-only dictionaries and visual keyboard resources.
 *
 * This patch is intentionally fail-closed: an updated/unknown original APK
 * must be audited before applying a known-version patch.
 * It does NOT prove all native or SDK persistence paths have been eliminated.
 */
public final class PrivacyNoHistoryPatch {
    private static final String FAC = "Lcom/android/inputmethod/latin/DictionaryFacilitatorImpl;";
    private static final String EXP = "Lcom/android/inputmethod/latin/ExpandableBinaryDictionary;";
    private static final String HIST = "Lcom/android/inputmethod/latin/personalization/UserHistoryDictionary;";
    private static final Set<String> TARGETS = new HashSet<>(Arrays.asList(
        FAC + "->addToUserHistory",
        FAC + "->addWordToUserHistory",
        EXP + "->updateEntriesForWord",
        EXP + "->updateEntriesForInputEvents",
        EXP + "->asyncFlushBinaryDictionary",
        EXP + "->addUnigramLocked",
        EXP + "->addNgramEntryLocked",
        HIST + "->addToDictionary"
    ));

    private static void validateTargets(DexFile dex) {
        Set<String> found = new HashSet<>();
        for (ClassDef cls : dex.getClasses()) {
            for (Method method : cls.getMethods()) {
                String id = cls.getType() + "->" + method.getName();
                if (!TARGETS.contains(id)) continue;
                if (!"V".equals(method.getReturnType()) || method.getImplementation() == null) {
                    throw new IllegalStateException("Unexpected target signature: " + id);
                }
                found.add(id);
            }
        }
        if (!found.equals(TARGETS)) {
            Set<String> missing = new HashSet<>(TARGETS);
            missing.removeAll(found);
            throw new IllegalStateException("Privacy patch incompatible with APK; missing " + missing);
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2)
            throw new IllegalArgumentException("PrivacyNoHistoryPatch source.dex output.dex");
        DexFile original = DexFileFactory.loadDexFile(new File(args[0]), null);
        validateTargets(original);

        DexFile modified = new DexRewriter(new RewriterModule() {
            @Override
            public Rewriter<Method> getMethodRewriter(Rewriters rewriters) {
                MethodRewriter base = new MethodRewriter(rewriters);
                return method -> {
                    Method rewritten = base.rewrite(method);
                    String id = rewritten.getDefiningClass() + "->" + rewritten.getName();
                    if (!TARGETS.contains(id)) return rewritten;
                    int registers = rewritten.getImplementation().getRegisterCount();
                    return new ImmutableMethod(
                        rewritten.getDefiningClass(),
                        rewritten.getName(),
                        rewritten.getParameters(),
                        rewritten.getReturnType(),
                        rewritten.getAccessFlags(),
                        rewritten.getAnnotations(),
                        rewritten.getHiddenApiRestrictions(),
                        new ImmutableMethodImplementation(
                            registers,
                            Collections.singletonList(new ImmutableInstruction10x(Opcode.RETURN_VOID)),
                            Collections.emptyList(),
                            Collections.emptyList()
                        )
                    );
                };
            }
        }).getDexFileRewriter().rewrite(original);
        validateTargets(modified);
        DexPool.writeTo(args[1], modified);

        // Verify the serialized DEX, not only in-memory rewriter objects.
        DexFile result = DexFileFactory.loadDexFile(new File(args[1]), null);
        validateTargets(result);
        int disabled = 0;
        for (ClassDef cls : result.getClasses()) {
            for (Method method : cls.getMethods()) {
                String id = cls.getType() + "->" + method.getName();
                if (!TARGETS.contains(id)) continue;
                Iterator<? extends Instruction> instructions =
                    method.getImplementation().getInstructions().iterator();
                if (!instructions.hasNext() || instructions.next().getOpcode() != Opcode.RETURN_VOID
                        || instructions.hasNext()) {
                    throw new IllegalStateException("Word history method still active: " + id);
                }
                System.out.println("BLOCKED " + id);
                disabled++;
            }
        }
        if (disabled != TARGETS.size()) throw new IllegalStateException("Missing privacy rewrites");
        System.out.println("PASS: eight known Java history/update/flush methods disabled");
        System.out.println("NOT VERIFIED: all potential native/third-party retention paths");
    }
}
