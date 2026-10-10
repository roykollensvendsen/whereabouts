# The phone app

"Hvor er jeg" sends where the phone is, which way it is going and how fast, to
whereabouts, while "Følg meg" is on. It goes on with the screen locked.

It sends a reading only when something has changed:
- the phone has moved 10 metres;
- it has turned 15 degrees while moving;
- its speed has changed by 5 km/h;
- or a minute has passed, so the service can tell a still phone from a silent one.

It talks to the service over the tailnet. The service lets in only the tailnet
login it is told to, so there is no key to type.

## Build it

Needs Java 17 and Android's tools, with `ANDROID_HOME` pointing at them.

<!-- not run: needs Android's tools; the android job in continuous integration builds it on every change -->
```bash
cd android
./gradlew assembleDebug testDebugUnitTest
```

The app is at `app/build/outputs/apk/debug/app-debug.apk`.
