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
        versionCode = 3
        versionName = "0.3"
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
}
