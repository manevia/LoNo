package lr.edu.ciu.lono.tv

import android.annotation.SuppressLint
import android.app.Activity
import android.os.Bundle
import android.view.KeyEvent
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient

/** Full-screen WebView showing LoNo in TV mode. Remote arrows/OK reach the page as key
 *  events (LoNo's TV mode handles them); the Back button goes back in the app's history. */
class MainActivity : Activity() {
    // Replace with your real HTTPS address.
    private val home = "https://lono.ciu.edu.lr/?tv=1"
    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                // Keep LoNo pages inside the app.
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) = false
            }
            isFocusable = true
            isFocusableInTouchMode = true
        }
        setContentView(web)
        if (savedInstanceState == null) web.loadUrl(home) else web.restoreState(savedInstanceState)
        web.requestFocus()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && web.canGoBack()) { web.goBack(); return true }
        return super.onKeyDown(keyCode, event)
    }
}
