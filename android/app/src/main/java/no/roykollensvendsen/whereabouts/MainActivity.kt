package no.roykollensvendsen.whereabouts

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.format.DateUtils
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.view.View
import android.view.WindowInsets
import android.view.WindowManager
import android.webkit.WebView
import android.widget.TextView
import java.util.concurrent.Executors

/** The address of the service, "Følg meg", and the map. Nothing else. */
class MainActivity : Activity() {

    private lateinit var address: EditText
    private lateinit var toggle: Button
    private lateinit var status: TextView
    private lateinit var warning: TextView
    private val ticking = Handler(Looper.getMainLooper())
    private lateinit var pretend: Pretend
    private lateinit var mapFrame: android.widget.FrameLayout
    private lateinit var closeFull: Button
    private var fullScreen = false
    private var trial: Teller? = null
    private var faster = Trip.FASTER[2]

    override fun onCreate(saved: Bundle?) {
        super.onCreate(saved)
        // The title bar only repeated the name, and hid the first lines; the version line names the app.
        actionBar?.hide()
        val pad = (16 * resources.displayMetrics.density).toInt()
        address = EditText(this).apply {
            hint = getString(R.string.address_hint)
            setText(Settings.address(this@MainActivity) ?: DEFAULT_ADDRESS)
        }
        toggle = Button(this).apply { setOnClickListener { flip() } }
        status = TextView(this)
        warning = TextView(this).apply {
            setTextColor(0xFFC92A2A.toInt())
            setOnClickListener { Power.openSaverSettings(this@MainActivity) }
        }
        val telling = CheckBox(this).apply {
            text = getString(R.string.telling)
            isChecked = Settings.telling(this@MainActivity)
            setOnCheckedChangeListener { _, on -> Settings.tell(this@MainActivity, on) }
        }
        // The map, inside the app: where Roy is in blue, a pretend drive in orange.
        val mapView = WebView(this).apply {
            settings.javaScriptEnabled = true
            visibility = View.GONE
        }
        fun showMap() {
            save()
            if (mapView.visibility != View.VISIBLE) {
                mapView.loadUrl(address.text.toString().trimEnd('/') + "/map")
                mapView.visibility = View.VISIBLE
            }
        }
        // Roy, 2026-10-10: the map on the whole screen when he chooses; back or "Lukk" leaves it.
        val close = Button(this).apply {
            text = getString(R.string.close_full)
            visibility = View.GONE
            setOnClickListener { leaveFullScreen() }
        }
        mapFrame = android.widget.FrameLayout(this).apply {
            addView(mapView)
            // Bottom middle: the map's own buttons sit in the corners, and "Følg meg" top right.
            addView(close, android.widget.FrameLayout.LayoutParams(
                android.widget.FrameLayout.LayoutParams.WRAP_CONTENT, android.widget.FrameLayout.LayoutParams.WRAP_CONTENT,
                android.view.Gravity.BOTTOM or android.view.Gravity.CENTER_HORIZONTAL,
            ).apply { bottomMargin = (48 * resources.displayMetrics.density).toInt() })
        }
        closeFull = close
        val full = Button(this).apply {
            text = getString(R.string.full_screen)
            setOnClickListener {
                showMap()
                enterFullScreen()
            }
        }
        val map = Button(this).apply {
            text = getString(R.string.show_map)
            setOnClickListener {
                if (mapView.visibility == View.VISIBLE) {
                    mapView.visibility = View.GONE
                    text = getString(R.string.show_map)
                } else {
                    showMap()
                    text = getString(R.string.hide_map)
                }
            }
        }
        val overHandsfree = CheckBox(this).apply {
            text = getString(R.string.over_handsfree)
            isChecked = Settings.handsfree(this@MainActivity)
            setOnCheckedChangeListener { _, on -> Settings.useHandsfree(this@MainActivity, on) }
        }
        // Roy, 2026-10-10: how often GPS is asked, how soon the coarser network steps in, and how far
        // back a spoken note is placed, all his to choose. They count from the next "Følg meg".
        val gpsEvery = choice(Settings.GPS_EVERY, { Settings.gpsEveryMs(this) }, { Settings.setGpsEveryMs(this, it) }) {
            getString(R.string.gps_every, it / 1000)
        }
        val fallback = choice(Settings.FALLBACK, { Settings.fallbackMs(this) }, { Settings.setFallbackMs(this, it) }) {
            getString(R.string.fallback_after, it / 1000)
        }
        val noteLag = choice(Settings.NOTE_LAG, { Settings.noteLagS(this) }, { Settings.setNoteLagS(this, it) }) {
            getString(R.string.note_lag, it)
        }
        // Roy, 2026-10-10: a way to hear, in the car, whether the telling comes through.
        val trySound = Button(this).apply {
            text = getString(R.string.try_sound)
            setOnClickListener {
                val tester = trial ?: Teller(this@MainActivity, Executors.newSingleThreadExecutor(), pretend = true)
                    .also { trial = it }
                // The speech engine needs a moment the first time.
                postDelayed({
                    status.text = getString(R.string.sound_goes, tester.route())
                    tester.say(getString(R.string.sound_test))
                }, 800)
            }
        }
        // A pretend drive, to hear what is told on the way.
        val pretendSaid = TextView(this)
        pretend = Pretend(this) { pretendSaid.text = it }
        val from = EditText(this).apply { hint = getString(R.string.pretend_from) }
        val to = EditText(this).apply { hint = getString(R.string.pretend_to) }
        val speed = Button(this).apply {
            text = getString(R.string.pretend_faster, faster)
            setOnClickListener {
                faster = Trip.FASTER[(Trip.FASTER.indexOf(faster) + 1) % Trip.FASTER.size]
                text = getString(R.string.pretend_faster, faster)
            }
        }
        val play = Button(this).apply {
            text = getString(R.string.pretend_start)
            setOnClickListener {
                save()
                if (pretend.running) {
                    pretend.stop()
                    pretendSaid.text = getString(R.string.pretend_stopped)
                    text = getString(R.string.pretend_start)
                    window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                } else {
                    pretend.start(from.text.toString().trim(), to.text.toString().trim(), faster)
                    text = getString(R.string.pretend_stop)
                    showMap()
                    map.text = getString(R.string.hide_map)
                    window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                }
            }
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
            // Roy, 2026-10-10: the bar at the top hid the first lines. From Android 15 the app draws under
            // the status bar and the navigation bar, so keep clear of them by their own size.
            setOnApplyWindowInsetsListener { view, insets ->
                if (fullScreen) {
                    view.setPadding(0, 0, 0, 0)
                } else if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
                    val bars = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
                    view.setPadding(pad + bars.left, pad + bars.top, pad + bars.right, pad + bars.bottom)
                } else {
                    @Suppress("DEPRECATION")
                    view.setPadding(
                        pad + insets.systemWindowInsetLeft, pad + insets.systemWindowInsetTop,
                        pad + insets.systemWindowInsetRight, pad + insets.systemWindowInsetBottom,
                    )
                }
                insets
            }
            // Roy, 2026-10-10: show which version runs, so nobody has to guess.
            addView(TextView(this@MainActivity).apply {
                text = getString(R.string.version, packageManager.getPackageInfo(packageName, 0).versionName)
                alpha = 0.7f
            })
            addView(address)
            addView(toggle)
            addView(telling)
            addView(overHandsfree)
            addView(side(gpsEvery, fallback))
            addView(noteLag)
            addView(trySound)
            addView(status)
            addView(warning)
            addView(TextView(this@MainActivity).apply {
                text = getString(R.string.pretend_title)
                setPadding(0, pad, 0, 0)
            })
            addView(side(from, to))
            addView(side(speed, play))
            addView(pretendSaid)
            addView(side(map, full))
            addView(mapFrame, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        })
        ask()
        Power.askToStayAwake(this)
        draw()
    }

    override fun onResume() {
        super.onResume()
        ticking.post(object : Runnable {
            override fun run() {
                draw()
                ticking.postDelayed(this, 5_000)
            }
        })
    }

    private fun enterFullScreen() {
        fullScreen = true
        val root = mapFrame.parent as LinearLayout
        for (i in 0 until root.childCount) {
            val child = root.getChildAt(i)
            if (child !== mapFrame) child.visibility = View.GONE
        }
        root.setPadding(0, 0, 0, 0)
        closeFull.visibility = View.VISIBLE
        bars(show = false)
        // Roy, 2026-10-10: in full screen the screen stays on, as a navigation app's does.
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    private fun leaveFullScreen() {
        if (!fullScreen) return
        fullScreen = false
        val root = mapFrame.parent as LinearLayout
        for (i in 0 until root.childCount) root.getChildAt(i).visibility = View.VISIBLE
        draw() // puts the warning line back to what it should be
        closeFull.visibility = View.GONE
        bars(show = true)
        if (!pretend.running) window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        root.requestApplyInsets()
    }

    @Suppress("DEPRECATION") // systemUiVisibility is the way before Android 11
    private fun bars(show: Boolean) {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
            val controller = window.insetsController ?: return
            val types = WindowInsets.Type.systemBars()
            if (show) {
                controller.show(types)
            } else {
                controller.hide(types)
                controller.systemBarsBehavior = android.view.WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            window.decorView.systemUiVisibility = if (show) 0 else
                View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (fullScreen) leaveFullScreen() else super.onBackPressed()
    }

    override fun onDestroy() {
        pretend.stop()
        trial?.close()
        super.onDestroy()
    }

    override fun onPause() {
        ticking.removeCallbacksAndMessages(null)
        save()
        super.onPause()
    }

    /** Roy, 2026-10-10: a drive begins with "Følg meg", so the map shows only this one. */
    private fun beginTrip() {
        val address = Settings.address(this) ?: return
        Thread {
            runCatching {
                val connection = java.net.URL(address.trimEnd('/') + "/trip").openConnection() as java.net.HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 10_000
                connection.responseCode
                connection.disconnect()
            }
        }.start()
    }

    private fun flip() {
        save()
        if (Following.running) {
            Following.stop(this)
        } else {
            Following.start(this)
            beginTrip()
        }
        ticking.postDelayed({ draw() }, 300)
    }

    private fun draw() {
        warning.text = Power.trouble(this)?.let { getString(R.string.power_warning, it) } ?: ""
        toggle.text = getString(if (Following.running) R.string.stop else R.string.follow)
        status.text = when {
            !Following.running -> "Følger deg ikke."
            Following.sent == 0L -> "Venter på første måling."
            else -> "Sist sendt " + DateUtils.getRelativeTimeSpanString(Following.sent) + "."
        }
    }

    /** A button that steps through `values` on each tap, saving the choice. */
    private fun choice(values: List<Long>, now: () -> Long, save: (Long) -> Unit, label: (Long) -> String) =
        Button(this).apply {
            text = label(now())
            isAllCaps = false
            setOnClickListener {
                val next = values[(values.indexOf(now()) + 1) % values.size]
                save(next)
                text = label(next)
            }
        }

    /** Two views side by side, sharing the width. */
    private fun side(left: View, right: View) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        addView(left, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        addView(right, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
    }

    private fun save() = Settings.save(this, address.text.toString().trim())

    private fun ask() {
        val wanted = listOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.POST_NOTIFICATIONS,
        ).filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (wanted.isNotEmpty()) requestPermissions(wanted.toTypedArray(), 1)
    }

    companion object {
        /** Roy's machine on his tailnet; anyone else types their own. */
        const val DEFAULT_ADDRESS = "https://precision7530-arch-roy.taild6993c.ts.net:10001/"
    }
}

/** Where the service is, whether to tell of places, and when each was last told. */
object Settings {
    private const val FILE = "whereabouts"
    private const val ADDRESS = "address"
    private const val TELLING = "telling"
    private const val TOLD = "told"
    // A new key, so a choice saved while the call was the default does not carry over.
    private const val HANDSFREE_AS_CALL = "handsfree_as_call"

    fun address(context: Context): String? =
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(ADDRESS, null)?.takeIf { it.isNotBlank() }

    fun save(context: Context, address: String) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().putString(ADDRESS, address).apply()
    }

    /** Whether a telling goes through the car's handsfree as a call. Roy, 2026-10-10: off; as music instead. */
    fun handsfree(context: Context): Boolean =
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getBoolean(HANDSFREE_AS_CALL, false)

    fun useHandsfree(context: Context, on: Boolean) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().putBoolean(HANDSFREE_AS_CALL, on).apply()
    }

    val GPS_EVERY = listOf(1_000L, 2_000L, 5_000L)
    val FALLBACK = listOf(5_000L, 10_000L, 20_000L)
    val NOTE_LAG = listOf(0L, 4L, 8L, 12L)

    private fun long(context: Context, key: String, default: Long): Long =
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getLong(key, default)

    private fun putLong(context: Context, key: String, value: Long) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().putLong(key, value).apply()
    }

    fun gpsEveryMs(context: Context) = long(context, "gps_every_ms", 1_000L)
    fun setGpsEveryMs(context: Context, value: Long) = putLong(context, "gps_every_ms", value)
    fun fallbackMs(context: Context) = long(context, "fallback_ms", 5_000L)
    fun setFallbackMs(context: Context, value: Long) = putLong(context, "fallback_ms", value)
    fun noteLagS(context: Context) = long(context, "note_lag_s", 8L)
    fun setNoteLagS(context: Context, value: Long) = putLong(context, "note_lag_s", value)

    fun telling(context: Context): Boolean =
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getBoolean(TELLING, true)

    fun tell(context: Context, on: Boolean) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().putBoolean(TELLING, on).apply()
    }

    /** When each place was last told, kept so a restart does not tell it again on the same pass. */
    fun told(context: Context): Map<Long, Long> {
        val kept = context.getSharedPreferences(FILE + "-" + TOLD, Context.MODE_PRIVATE).all
        return kept.mapNotNull { (id, at) -> id.toLongOrNull()?.let { key -> (at as? Long)?.let { key to it } } }.toMap()
    }

    fun markTold(context: Context, id: Long, at: Long) {
        context.getSharedPreferences(FILE + "-" + TOLD, Context.MODE_PRIVATE).edit().putLong(id.toString(), at).apply()
    }
}
