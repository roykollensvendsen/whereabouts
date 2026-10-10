package no.roykollensvendsen.whereabouts

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class GpsWatchTest {
    @Test
    fun aMinuteWithoutAFixIsSilence() {
        assertFalse(GpsWatch.silent(lastGps = 100_000, startedAt = 0, now = 150_000))
        assertTrue(GpsWatch.silent(lastGps = 100_000, startedAt = 0, now = 160_000))
    }

    @Test
    fun beforeTheFirstFixSilenceCountsFromTheStart() {
        assertFalse(GpsWatch.silent(lastGps = 0, startedAt = 100_000, now = 130_000))
        assertTrue(GpsWatch.silent(lastGps = 0, startedAt = 100_000, now = 170_000))
    }

    @Test
    fun theReasonNamesPowerSavingWhenItTurnsGpsOff() {
        assertEquals(
            "Strømsparing er på og slår av GPS når skjermen er av.",
            GpsWatch.reason(gpsEnabled = true, power = "strømsparing slår av GPS når skjermen er av"),
        )
        assertEquals("GPS er slått av i telefonens innstillinger.", GpsWatch.reason(false, null))
        assertEquals("Kanskje er du innendørs, i en tunnel eller under tett tak.", GpsWatch.reason(true, null))
    }

    @Test
    fun theWarningSaysHowLongAndWhatIsDoneMeanwhile() {
        assertEquals(
            "GPS-en har ikke svart på 3 minutter. Grunn. Jeg bruker grovere posisjon fra mobilnettet så lenge.",
            GpsWatch.warning(180_000, "Grunn.", network = true),
        )
        assertEquals("GPS-en har ikke svart på et minutt. Grunn.", GpsWatch.warning(60_000, "Grunn.", network = false))
    }
}
