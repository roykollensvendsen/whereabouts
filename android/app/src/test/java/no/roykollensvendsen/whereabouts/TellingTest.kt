package no.roykollensvendsen.whereabouts

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TellingTest {
    // 0.001 degrees of latitude is about 111 metres.
    private val bru = Place(1, "Nidelva bru", 58.451, 9.0, 150.0, "Til høyre renner Nidelva ut i havet.")
    private val merdo = Place(2, "Merdø", 58.500, 9.0, 400.0, "Ute ligger Merdø.")
    private val still = Reading(58.450, 9.0, heading = 0.0, speed = 0.0, at = 10_000_000L)

    @Test
    fun aPlaceWithinItsRadiusIsDue() {
        assertEquals(listOf(bru), Telling.due(listOf(bru, merdo), still, emptyMap()))
    }

    @Test
    fun aPlaceBeyondItsRadiusIsNotDue() {
        val far = still.copy(latitude = 58.448) // about 330 metres short
        assertTrue(Telling.due(listOf(bru), far, emptyMap()).isEmpty())
    }

    @Test
    fun atSpeedAPlaceIsToldBeforeRoyIsLevelWithIt() {
        val driving = still.copy(latitude = 58.4485, speed = 80 / 3.6) // 80 km/h, 280 m away
        assertEquals(listOf(bru), Telling.due(listOf(bru), driving, emptyMap()))
    }

    @Test
    fun onePassTellsAPlaceOnce() {
        val told = mapOf(bru.id to still.at - 60_000L)
        assertTrue(Telling.due(listOf(bru), still, told).isEmpty())
    }

    @Test
    fun theNextPassTellsItAgain() {
        val told = mapOf(bru.id to still.at - Telling.QUIET_MS)
        assertEquals(listOf(bru), Telling.due(listOf(bru), still, told))
    }

    @Test
    fun severalDuePlacesAreToldNearestFirst() {
        val wide = merdo.copy(radiusM = 6_000.0)
        assertEquals(listOf(bru, wide), Telling.due(listOf(wide, bru), still, emptyMap()))
    }

    @Test
    fun placesAreFetchedAgainAfterAWhileOrAfterTenKilometres() {
        assertTrue(Telling.refetch(null, still))
        assertFalse(Telling.refetch(still, still.copy(at = still.at + 60_000L)))
        assertTrue(Telling.refetch(still, still.copy(at = still.at + Telling.REFETCH_MS)))
        assertTrue(Telling.refetch(still, still.copy(latitude = 58.55, at = still.at + 1_000L)))
    }

    @Test
    fun aTellingSaysWhichWayFromTheCarAndHowFar() {
        // Heading north; the bridge 110 m ahead.
        val driving = still.copy(speed = 20.0)
        assertEquals("Rett frem, 100 meter unna: Nidelva bru. Til høyre renner Nidelva ut i havet.",
            Telling.spoken(bru, driving))
        // Heading east instead: the bridge is to the left.
        assertEquals("Til venstre, 100 meter unna: Nidelva bru. Til høyre renner Nidelva ut i havet.",
            Telling.spoken(bru, driving.copy(heading = 90.0)))
    }

    @Test
    fun aTellingDoesNotSayTheNameTwice() {
        val lake = merdo.copy(said = "Merdø er en øy med uthavn.")
        val far = still.copy(latitude = 58.488, speed = 20.0)
        assertEquals("Rett frem, 1,3 kilometer unna: Merdø er en øy med uthavn.", Telling.spoken(lake, far))
    }

    @Test
    fun standingStillTheDirectionIsByCompass() {
        assertEquals("Mot nord, 100 meter unna: Nidelva bru. Til høyre renner Nidelva ut i havet.",
            Telling.spoken(bru, still))
    }

    @Test
    fun aNoteIsReadAsRoySaidIt() {
        val note = bru.copy(kind = "note", said = "En melding du la igjen her: kjøp ved.")
        assertEquals("En melding du la igjen her: kjøp ved.", Telling.spoken(note, still.copy(speed = 20.0)))
    }
}
