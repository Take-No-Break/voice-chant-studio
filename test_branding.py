from pathlib import Path
import tempfile,unittest
from core import Project
BASE=Path(__file__).parent
class BrandingTests(unittest.TestCase):
    def test_addon_export_includes_matching_tga_and_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Project(Path(folder)/'project',[])
            target,count=p.export(Path(folder)/'export',BASE/'addon',game=False)
            self.assertEqual(count,0)
            self.assertEqual((target/'Icon.tga').read_bytes(),(BASE/'addon/Icon.tga').read_bytes())
            toc=(target/'VoiceChantStudio.toc').read_text()
            self.assertIn('## IconTexture: Interface\\AddOns\\VoiceChantStudio\\Icon.tga',toc)
            data=(target/'Icon.tga').read_bytes()
            self.assertEqual(data[2],2)
            self.assertEqual(int.from_bytes(data[12:14],'little'),64)
            self.assertEqual(int.from_bytes(data[14:16],'little'),64)
            self.assertEqual(data[16],32)
    def test_windows_icon_and_original_source_are_shipped(self):
        ico=(BASE/'assets/branding/app-icon.ico').read_bytes()
        self.assertEqual(ico[:4],b'\0\0\1\0')
        self.assertGreaterEqual(int.from_bytes(ico[4:6],'little'),6)
        self.assertTrue((BASE/'assets/branding/app-icon.svg').is_file())
        self.assertIn("icon='assets/branding/app-icon.ico'",(BASE/'VoiceChantStudio.spec').read_text())
