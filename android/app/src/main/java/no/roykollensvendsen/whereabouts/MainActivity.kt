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
import android.view.WindowManager
import android.webkit.WebView
import android.widget.TextView

/** The address of the service, "Følg meg", and the map. Nothing else. */
class MainActivity : Activity() {

    private lateinit var address: EditText
    private lateinit var toggle: Button
    private lateinit var status: TextView
    private val ticking = Handler(Looper.getMainLooper())
    private lateinit var pretend: Pretend
    private var faster = Trip.FASTER[2]

    override fun onCreate(saved: Bundle?) {
        super.onCreate(saved)
        val pad = (16 * resources.displayMetrics.density).toInt()
        address = EditText(this).apply {
            hint = getString(R.string.address_hint)
            setText(Settings.address(this@MainActivity) ?: DEFAULT_ADDRESS)
        }
        toggle = Button(this).apply { setOnClickListener { flip() } }
        status = TextView(this)
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
            setPadding(pad, pad * 2, pad, pad)
            addView(address)
            addView(toggle)
            addView(telling)
            addView(status)
            addView(TextView(this@MainActivity).apply {
                text = getString(R.string.pretend_title)
                setPadding(0, pad, 0, 0)
            })
            addView(side(from, to))
            addView(side(speed, play))
            addView(pretendSaid)
            addView(map)
            addView(mapView, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        })
        ask()
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

    override fun onDestroy() {
        pretend.stop()
        super.onDestroy()
    }

    override fun onPause() {
        ticking.removeCallbacksAndMessages(null)
        save()
        super.onPause()
    }

    private fun flip() {
        save()
        if (Following.running) Following.stop(this) else Following.start(this)
        ticking.postDelayed({ draw() }, 300)
    }

    private fun draw() {
        toggle.text = getString(if (Following.running) R.string.stop else R.string.follow)
        status.text = when {
            !Following.running -> "Følger deg ikke."
            Following.sent == 0L -> "Venter på første måling."
            else -> "Sist sendt " + DateUtils.getRelativeTimeSpanString(Following.sent) + "."
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

    fun address(context: Context): String? =
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(ADDRESS, null)?.takeIf { it.isNotBlank() }

    fun save(context: Context, address: String) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().putString(ADDRESS, address).apply()
    }

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
