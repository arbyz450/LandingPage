plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.crstockfish.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.crstockfish.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
        ndk {
            // 64-bit ARM covers every phone from the last ~8 years; add "x86_64" for emulators.
            abiFilters += listOf("arm64-v8a")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

// The engine lives two directories up (cr-stockfish/crsf, cr-stockfish/knowledge).
// Chaquopy bundles whatever is in its python source dirs, so we sync those two
// folders into build/crsf_py before every build instead of pointing at ../../
// (which would also drag in tests, reports, templates and this android folder).
val crsfPy = layout.buildDirectory.dir("crsf_py")
val syncCrsf by tasks.registering(Sync::class) {
    into(crsfPy)
    from("../../crsf") {
        into("crsf")
        exclude("**/__pycache__/**", "**/*.pyc")
    }
    from("../../knowledge") {
        into("knowledge")
        include("*.json")
    }
}
tasks.named("preBuild") { dependsOn(syncCrsf) }

chaquopy {
    defaultConfig {
        // 3.8: the only Python for which Chaquopy's index carries an opencv-python wheel
        // (3.11 reports "from versions: none"). The engine code stays 3.8-compatible.
        version = "3.8"
        pip {
            // Only prebuilt Android wheels from Chaquopy's index: source tarballs cannot
            // be compiled for Android in the build. Unpinned, pip picks the newest
            // wheel that exists (and lists the available versions if none does).
            options("--only-binary", ":all:")
            install("numpy")
            install("opencv-python")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("src/main/python")
            srcDir(crsfPy)
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.lifecycle:lifecycle-livedata-ktx:2.8.4")
}
