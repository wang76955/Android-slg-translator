import unittest
import zipfile
from pathlib import Path


APK = Path(__file__).parents[1] / "slg-workshop-ui-signed.apk"


class BuiltApkTest(unittest.TestCase):
    def test_signed_apk_contains_workshop_assets(self):
        self.assertTrue(APK.exists(), "signed workshop APK must exist")
        with zipfile.ZipFile(APK) as archive:
            js = archive.read(
                "assets/public/assets/index-CJtfdHOF.js"
            ).decode("utf-8")
            css = archive.read(
                "assets/public/assets/index-C044IUg3.css"
            ).decode("utf-8")
            self.assertIn("让喜欢的故事，用中文继续。", js)
            self.assertIn("workshop-runtime", js)
            self.assertIn("--workshop-primary", css)
            self.assertEqual(
                archive.getinfo("resources.arsc").compress_type,
                zipfile.ZIP_STORED,
            )
            self.assertIn("classes7.dex", archive.namelist())
            self.assertIn(b"FastApkScanner", archive.read("classes6.dex"))
            self.assertIn(b"FastApkScanner", archive.read("classes7.dex"))
            self.assertIn("t.packageName", js)
            self.assertIn("workshop-scan-elapsed", js)
            for token in (
                "slg-workshop-settings-v1",
                "settingsProvider",
                "settingsCustomBaseURL",
                "function cacheV2Key(e,t){return _o+`v2|`+cacheIdentity(e,t)}",
                "function isNetworkFailure(e)",
                "maxRetries:1",
                'if(isInstall&&!target){installButton=null;lastSnapshot="";refresh();return}',
            ):
                self.assertIn(token, js)
            self.assertIn(
                'isInstall?findButton("安装补丁版"):button',
                js,
            )
            self.assertNotIn(
                'isInstall?(findButton("安装补丁版")||button):button',
                js,
            )


if __name__ == "__main__":
    unittest.main()
