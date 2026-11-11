package dev.tzn5.rebind;

import java.io.File;
import java.util.HashSet;
import java.util.Set;
import org.jf.dexlib2.DexFileFactory;
import org.jf.dexlib2.iface.ClassDef;
import org.jf.dexlib2.iface.DexFile;
import org.jf.dexlib2.rewriter.DexRewriter;
import org.jf.dexlib2.rewriter.Rewriter;
import org.jf.dexlib2.rewriter.RewriterModule;
import org.jf.dexlib2.rewriter.Rewriters;
import org.jf.dexlib2.writer.pool.DexPool;

/**
 * Replace the original LatinIME class with a renamed base and give the new
 * Glass subclass the original service identity, preserving Android IME
 * selection after upgrade.
 *
 * Dexlib2 rewrites every type reference and reorders all DEX string/type
 * pools correctly. NEVER use raw string replacement in a DEX file.
 */
public final class DexServiceRebind {
    private static final String ORIGINAL = "Lcom/android/inputmethod/latin/LatinIME;";
    private static final String BASE = "Lcom/android/inputmethod/latin/XiaomiIMECore;";
    private static final String GLASS = "Lcom/android/inputmethod/latin/GlassIME;";

    private static DexFile rewrite(DexFile src, boolean addon) {
        return new DexRewriter(new RewriterModule() {
            @Override public Rewriter<String> getTypeRewriter(Rewriters r) {
                return value -> {
                    if (ORIGINAL.equals(value)) return BASE;
                    if (addon && GLASS.equals(value)) return ORIGINAL;
                    return value;
                };
            }
        }).getDexFileRewriter().rewrite(src);
    }

    private static ClassDef requireClass(DexFile file, String name) {
        for (ClassDef cls : file.getClasses()) {
            if (name.equals(cls.getType())) return cls;
        }
        throw new IllegalStateException("Missing class: " + name);
    }

    private static void checkUniqueness(DexFile a, DexFile b) {
        Set<String> classes = new HashSet<>();
        for (ClassDef cls : a.getClasses()) {
            if (!classes.add(cls.getType())) throw new IllegalStateException("Duplicate: " + cls.getType());
        }
        for (ClassDef cls : b.getClasses()) {
            if (!classes.add(cls.getType())) throw new IllegalStateException("Duplicate: " + cls.getType());
        }
        if (classes.contains(GLASS)) throw new IllegalStateException("Old service identity survived rebind");
        if (!classes.contains(BASE) || !classes.contains(ORIGINAL))
            throw new IllegalStateException("Missing renamed base / original component");
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 4) {
            throw new IllegalArgumentException(
                "Usage: DexServiceRebind base.dex glass-addon.dex output-base.dex output-addon.dex");
        }
        DexFile original = DexFileFactory.loadDexFile(new File(args[0]), null);
        DexFile addon = DexFileFactory.loadDexFile(new File(args[1]), null);
        requireClass(original, ORIGINAL);
        requireClass(addon, GLASS);
        DexFile baseRewritten = rewrite(original, false);
        DexFile addonRewritten = rewrite(addon, true);
        requireClass(baseRewritten, BASE);
        ClassDef service = requireClass(addonRewritten, ORIGINAL);
        if (!BASE.equals(service.getSuperclass())) {
            throw new IllegalStateException("Glass subclass no longer inherits original LatinIME");
        }
        checkUniqueness(baseRewritten, addonRewritten);
        DexPool.writeTo(args[2], baseRewritten);
        DexPool.writeTo(args[3], addonRewritten);

        // Read back the actual serialized DEX files to detect invalid output.
        DexFile readBase = DexFileFactory.loadDexFile(new File(args[2]), null);
        DexFile readAddon = DexFileFactory.loadDexFile(new File(args[3]), null);
        requireClass(readBase, BASE);
        ClassDef verified = requireClass(readAddon, ORIGINAL);
        if (!BASE.equals(verified.getSuperclass())) throw new IllegalStateException("Bad superclass after DEX serialization");
        checkUniqueness(readBase, readAddon);
        System.out.println("PASS: Android IME service remains original LatinIME component.");
        System.out.println("PASS: original engine renamed XiaomiIMECore and extended by Glass UI.");
        System.out.println("PASS: both DEX outputs re-read successfully, with unique class identities.");
    }
}
