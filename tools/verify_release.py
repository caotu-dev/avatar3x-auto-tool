"""Verify a portable release without extracting or executing untrusted files."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip',type=Path,default=Path('dist/release/Avatools-3x-windows-x64.zip'))
    parser.add_argument('--installed',type=Path)
    args=parser.parse_args()
    package=args.zip
    with package.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    expected=package.with_name('SHA256SUMS.txt').read_text(encoding='utf-8-sig').split()
    assert expected==[digest,package.name], 'SHA-256 or archive name mismatch'
    required=['Avatools 3x.exe','README.md','README.txt','release-files.json',
              'docs/images/dashboard-v2.png','docs/images/missions-v2.png',
              'docs/images/settings-v2.png','vision/windows_ocr.ps1',
              'ui/assets/currency_coins.png','ui/assets/currency_gold.png']
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None, 'ZIP CRC failure'
        names=archive.namelist()
        assert len(names)==len(set(names)), 'Duplicate ZIP entries'
        for name in names:
            path=PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts
            assert path.parts[0]=='Avatools3x'
            assert len(path.parts)<2 or path.parts[1] not in ('runtime','debug','.local-qa')
        assert all('Avatools3x/'+name in names for name in required), 'Missing portable files'
        if args.installed:
            for name in required:
                assert archive.read('Avatools3x/'+name)==(args.installed/name).read_bytes(), 'Installed file mismatch: '+name
        print(json.dumps(dict(integrity='passed',sha256=digest,bytes=package.stat().st_size,
                              entries=len(names),user_guide_included=True,private_runtime=False),indent=2))


if __name__=='__main__':
    main()
