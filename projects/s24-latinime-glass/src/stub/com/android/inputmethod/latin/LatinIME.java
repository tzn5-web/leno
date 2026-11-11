package com.android.inputmethod.latin;
import android.inputmethodservice.InputMethodService;
import android.view.View;
import android.view.inputmethod.EditorInfo;
/** Test-only ABI stub; NEVER package this class in a release APK.
 * Its method surface now mirrors the original Xiaomi IME lifecycle
 * so the DEX rebinding and cross-file verifier can be exercised in CI.
 */
public class LatinIME extends InputMethodService {
    @Override public void onCreate() { super.onCreate(); }
    @Override public View onCreateInputView() { return super.onCreateInputView(); }
    @Override public void setInputView(View view) { super.setInputView(view); }
    @Override public void onStartInputView(EditorInfo info, boolean restart) {
        super.onStartInputView(info, restart);
    }
    @Override public void onFinishInputView(boolean finishing) {
        super.onFinishInputView(finishing);
    }
}
