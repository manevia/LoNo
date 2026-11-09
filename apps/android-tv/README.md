# LoNo for Android TV, Google TV and Fire TV

Android TVs don't ship Chrome, so a Trusted Web Activity can't be used. This is a
minimal WebView app instead. These are the source files only. Create a new **Empty
Views Activity** project in Android Studio with:

- package `lr.edu.ciu.lono.tv`
- minimum SDK 23
- language Kotlin

Then replace the project's `AndroidManifest.xml`, `MainActivity.kt` and `res/drawable/`
with the files here, and set `home` in `MainActivity.kt` to your HTTPS address.

The full steps are in `docs/DEVICES.md`. These files haven't been built in CI; expect
to adjust Gradle settings to your Android Studio version.
