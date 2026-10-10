package no.roykollensvendsen.whereabouts

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.format.DateUtils
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

/** The address of the service, "Følg meg", and the map. Nothing else. */
class MainActivity : Activity() {

    private lateinit var address: EditText
    private lateinit var toggle: Button
    private lateinit var status: TextView
    private val ticking = Handler(Looper.getMainLooper())

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
        val map = Button(this).apply {
            text = getString(R.string.show_map)
            setOnClickListener {
                save()
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(address.text.toString().trimEnd('/') + "/map")))
            }
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad * 2, pad, pad)
            addView(address)
            addView(toggle)
            addView(telling)
            addView(map)
            addView(status)
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
