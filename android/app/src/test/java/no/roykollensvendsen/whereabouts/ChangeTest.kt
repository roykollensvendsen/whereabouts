package no.roykollensvendsen.whereabouts

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ChangeTest {
    private val driving = Reading(58.6, 9.0, heading = 90.0, speed = 16.7, at = 0L)

    @Test
    fun theFirstReadingIsAlwaysSent() {
        assertTrue(Change.worthSending(null, driving))
    }

    @Test
    fun nothingChangedIsNotSent() {
        assertFalse(Change.worthSending(driving, driving.copy(at = 2_000L)))
    }

    @Test
    fun aMoveOfTenMetresIsSent() {
        // 0.0001 degrees of latitude is about 11 metres.
        assertTrue(Change.worthSending(driving, driving.copy(latitude = 58.6001, at = 2_000L)))
        assertFalse(Change.worthSending(driving, driving.copy(latitude = 58.60003, at = 2_000L)))
    }

    @Test
    fun aTurnOfFifteenDegreesWhileMovingIsSent() {
        assertTrue(Change.worthSending(driving, driving.copy(heading = 106.0, at = 2_000L)))
        assertFalse(Change.worthSending(driving, driving.copy(heading = 100.0, at = 2_000L)))
    }

    @Test
    fun aTurnStandingStillIsNoise() {
        val still = driving.copy(speed = 0.0)
        assertFalse(Change.worthSending(still, still.copy(heading = 200.0, at = 2_000L)))
    }

    @Test
    fun fiveKilometresAnHourFasterIsSent() {
        assertTrue(Change.worthSending(driving, driving.copy(speed = 16.7 + 1.5, at = 2_000L)))
        assertFalse(Change.worthSending(driving, driving.copy(speed = 16.7 + 1.0, at = 2_000L)))
    }

    @Test
    fun aMinuteWithoutChangeSendsAHeartbeat() {
        assertTrue(Change.worthSending(driving, driving.copy(at = Change.HEARTBEAT_MS)))
    }

    @Test
    fun anglesWrapAroundNorth() {
        assertEquals(20.0, Change.angle(350.0, 10.0), 0.001)
    }
}
