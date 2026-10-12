plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "no.roykollensvendsen.whereabouts"
    compileSdk = 35

    defaultConfig {
        applicationId = "no.roykollensvendsen.whereabouts"
        // Android 10: the oldest that gives a foreground service a location type.
        minSdk = 29
        targetSdk = 35
        versionCode = 25
        versionName = "0.25"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    // The real org.json, since the one in android.jar only throws in unit tests.
    testImplementation("org.json:json:20240303")
}
