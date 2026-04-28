"""
p4a Build Hook — Injects critical attributes into AndroidManifest.xml
This runs automatically during 'buildozer android debug' after the manifest is generated.

Injections:
  1. foregroundServiceType="dataSync"  → Fix Android 14+ crash
  2. exported="false"                  → Fix Android 12+ security requirement
  3. stopWithTask="false"              → Service SURVIVES app swipe-away
  4. Remove extractNativeLibs          → Fix build warning
"""
import os


def after_apk_build(toolchain):
    """Inject attributes into the Service declaration in AndroidManifest.xml."""
    try:
        dist_dir = toolchain._dist.dist_dir
        manifest_path = os.path.join(dist_dir, "src", "main", "AndroidManifest.xml")

        if not os.path.exists(manifest_path):
            print("[p4a_hook] AndroidManifest.xml not found, skipping.")
            return

        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()

        modified = False

        # --- 1. Inject foregroundServiceType + exported + stopWithTask ---
        service_tag = 'android:name="com.turbo.gamebooster.ServiceBooster"'

        if service_tag in content:
            # Build the replacement with all needed attributes
            new_attrs = []

            if 'foregroundServiceType' not in content:
                new_attrs.append('android:foregroundServiceType="dataSync"')

            if 'android:exported' not in content.split(service_tag)[1].split('/>')[0]:
                new_attrs.append('android:exported="false"')

            if 'stopWithTask' not in content:
                new_attrs.append('android:stopWithTask="false"')

            if new_attrs:
                injection = '\n                 '.join(new_attrs)
                content = content.replace(
                    service_tag,
                    f'{service_tag}\n                 {injection}'
                )
                modified = True
                print(f"[p4a_hook] ✅ Injected into ServiceFsociety: {', '.join(new_attrs)}")

        # --- 2. Remove deprecated extractNativeLibs warning ---
        for pattern in ['android:extractNativeLibs="true" ', 'android:extractNativeLibs="true"']:
            if pattern in content:
                content = content.replace(pattern, '')
                modified = True
                print("[p4a_hook] ✅ Removed deprecated extractNativeLibs")
                break

        # --- 3. Write back ---
        if modified:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("[p4a_hook] ✅ AndroidManifest.xml patched successfully!")
        else:
            print("[p4a_hook] ℹ️ Manifest already patched, no changes needed.")

    except Exception as e:
        # Non-fatal — print warning but don't break the build
        print(f"[p4a_hook] ⚠️ Hook error (non-fatal): {e}")
