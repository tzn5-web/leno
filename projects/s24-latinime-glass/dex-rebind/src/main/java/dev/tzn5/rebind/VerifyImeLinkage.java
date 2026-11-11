package dev.tzn5.rebind;

import java.io.File;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import org.jf.dexlib2.DexFileFactory;
import org.jf.dexlib2.iface.ClassDef;
import org.jf.dexlib2.iface.DexFile;
import org.jf.dexlib2.iface.Method;
import org.jf.dexlib2.iface.MethodParameter;

/**
 * Fail-closed contract check for the actual Xiaomi IME (base DEX) and Glass
 * extension DEX. Unlike a compile-only test this validates the serialized,
 * rebound bytecode that an Android class loader would see.
 *
 * This is static linkage validation, not an Android runtime/install test.
 */
public final class VerifyImeLinkage {
    private static final String SERVICE = "Lcom/android/inputmethod/latin/LatinIME;";
    private static final String ORIGINAL_ENGINE = "Lcom/android/inputmethod/latin/XiaomiIMECore;";
    private static final String WRONG_SERVICE = "Lcom/android/inputmethod/latin/GlassIME;";
    private static final int ACC_PRIVATE = 0x2;
    private static final int ACC_STATIC = 0x8;
    private static final int ACC_FINAL = 0x10;
    private static final int ACC_ABSTRACT = 0x400;

    private static final class Signature {
        final String name;
        final String result;
        final String[] parameters;
        Signature(String name, String result, String... parameters) {
            this.name = name;
            this.result = result;
            this.parameters = parameters;
        }
        boolean matches(Method m) {
            if (!m.getName().equals(name) || !m.getReturnType().equals(result)
                    || m.getParameters().size() != parameters.length) return false;
            for (int i=0; i<parameters.length; i++)
                if (!m.getParameters().get(i).getType().equals(parameters[i])) return false;
            return true;
        }
        String description() { return name + Arrays.toString(parameters) + " -> " + result; }
    }

    private static final Signature[] OVERRIDES = {
        new Signature("onCreate", "V"),
        new Signature("onCreateInputView", "Landroid/view/View;"),
        new Signature("setInputView", "V", "Landroid/view/View;"),
        new Signature("onStartInputView", "V", "Landroid/view/inputmethod/EditorInfo;", "Z"),
        new Signature("onFinishInputView", "V", "Z")
    };

    private static Method findMethod(ClassDef c, Signature target) {
        for (Method m : c.getMethods()) if (target.matches(m)) return m;
        return null;
    }

    private static void check(DexFile original, DexFile addon) {
        Map<String,ClassDef> all = new HashMap<>();
        for (ClassDef c: original.getClasses()) {
            if (all.put(c.getType(), c) != null)
                throw new IllegalStateException("Duplicate base class: " + c.getType());
        }
        for (ClassDef c: addon.getClasses()) {
            if (all.put(c.getType(), c) != null)
                throw new IllegalStateException("Duplicate class across DEX files: " + c.getType());
        }

        ClassDef base = all.get(ORIGINAL_ENGINE);
        ClassDef service = all.get(SERVICE);
        if (base == null || service == null)
            throw new IllegalStateException("Missing original Xiaomi core or Android LatinIME service");
        if (all.containsKey(WRONG_SERVICE))
            throw new IllegalStateException("Stale GlassIME component would cause IME identity mismatch");
        if (!SERVICE.equals(service.getType()) || !ORIGINAL_ENGINE.equals(service.getSuperclass()))
            throw new IllegalStateException("Glass service must extend the Xiaomi original core");
        if ((base.getAccessFlags() & ACC_FINAL) != 0)
            throw new IllegalStateException("Original Xiaomi core is final and cannot be extended");
        if ((service.getAccessFlags() & ACC_ABSTRACT) != 0)
            throw new IllegalStateException("Exported Android IME service is abstract");

        for (Signature target: OVERRIDES) {
            Method child = findMethod(service, target);
            if (child == null || child.getImplementation() == null)
                throw new IllegalStateException("Missing executable Glass override: " + target.description());
            if ((child.getAccessFlags() & (ACC_PRIVATE | ACC_STATIC | ACC_ABSTRACT)) != 0)
                throw new IllegalStateException("Invalid Glass override access: " + target.description());
            Method parent = findMethod(base, target);
            if (parent != null) {
                if ((parent.getAccessFlags() & (ACC_PRIVATE | ACC_STATIC | ACC_FINAL)) != 0)
                    throw new IllegalStateException("Original Xiaomi method cannot be overridden: "
                            + target.description());
                if (parent.getImplementation() == null)
                    throw new IllegalStateException("Original Xiaomi method has no code: "
                            + target.description());
            }
            System.out.println("PASS: executable Glass override compatible: " + target.description());
        }

        // Standard Android source builds may pack GlassActivity and emoji in the
        // addon classes2.dex. Test that both are available to the app class loader.
        for (String name : new String[] {
                "Lcom/android/inputmethod/latin/setup/GlassActivity;",
                "Lcom/android/inputmethod/latin/GlassEmojiPanel;"
        }) {
            ClassDef c = all.get(name);
            if (c == null) throw new IllegalStateException("Missing required UI class: " + name);
        }
        System.out.println("PASS: unique Android LatinIME service; Xiaomi core present; "
                + all.size() + " unique DEX classes");
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2)
            throw new IllegalArgumentException(
                    "Usage: VerifyImeLinkage rebound-original.dex rebound-addon.dex");
        DexFile original = DexFileFactory.loadDexFile(new File(args[0]), null);
        DexFile addon = DexFileFactory.loadDexFile(new File(args[1]), null);
        check(original, addon);
    }
}
