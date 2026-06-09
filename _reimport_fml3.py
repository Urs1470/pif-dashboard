"""Re-import FML3 project with read-only param filtering."""
import json
import os
import sys
import urllib.request
import urllib.error
import uuid

API_TOKEN = os.environ.get('PIF_API_TOKEN', '7261d39496da60ffab55ce2c74a613b694b87eb41bbc654ebad0c75c905191fa')
BASE_URL = "https://pif.iupif.org"
PROJECT_ID = "066097ce-1b07-4e0a-83a3-bb92bf156079"
ARCHIVE_PATH = r"C:\Users\ion.ursu\Downloads\FML3.zip"


def api_request(url, method=None, data=None, files_data=None):
    if method is None:
        method = "POST" if (data is not None or files_data) else "GET"
    if files_data:
        boundary = uuid.uuid4().hex
        parts = []
        for field_name, fname, fdata in files_data:
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field_name}\"; filename=\"{fname}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n".encode()
            )
            parts.append(fdata)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {API_TOKEN}",
            "User-Agent": "PIF-Reimport/1.0",
        }
    elif data is not None:
        body = json.dumps(data).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_TOKEN}",
        }
    else:
        body = None
        headers = {"Authorization": f"Bearer {API_TOKEN}"}

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    resp = urllib.request.urlopen(req, timeout=120)
    return json.loads(resp.read().decode())


def main():
    # Step 1: Preview import with new filtering
    print("=== Step 1: Preview archive import ===")
    with open(ARCHIVE_PATH, 'rb') as f:
        archive_data = f.read()

    result = api_request(
        f"{BASE_URL}/api/import-archive/preview",
        files_data=[("file", "FML3.zip", archive_data)]
    )
    print(f"Project: {result.get('project_name')}, Drives: {result.get('count')}")
    for d in result.get('drives', []):
        params = d.get('params', {})
        desc_count = len(d.get('descrieri', {}))
        print(f"  {d['nume']:20} params={len(params):3d}  descrieri={desc_count:3d}  skipped={d.get('skipped_default', 0)}")

    total_params = sum(len(d.get('params', {})) for d in result.get('drives', []))
    total_skipped = sum(d.get('skipped_default', 0) for d in result.get('drives', []))
    print(f"\nTotal: {total_params} params kept, {total_skipped} skipped")

    if '--apply' not in sys.argv:
        print("\nDry run. Use --apply to delete old equipment and re-import.")
        return

    # Step 2: Delete existing equipment
    print("\n=== Step 2: Delete existing equipment ===")
    equipment = api_request(f"{BASE_URL}/api/proiecte/{PROJECT_ID}/echipamente")
    for eq in equipment:
        try:
            api_request(f"{BASE_URL}/api/echipamente/{eq['id']}", method="DELETE")
            print(f"  Deleted: {eq['nume']}")
        except Exception as e:
            print(f"  Error: {eq['nume']} -> {e}")

    # Step 3: Import with filtered params
    print("\n=== Step 3: Import drives ===")
    persist = api_request(
        f"{BASE_URL}/api/proiecte/{PROJECT_ID}/echipamente/import-archive",
        data={"drives": result["drives"]}
    )
    print(f"  {persist.get('message')}")

    # Step 4: Verify
    print("\n=== Step 4: Verify ===")
    equipment = api_request(f"{BASE_URL}/api/proiecte/{PROJECT_ID}/echipamente")
    for eq in equipment[:3]:
        params = json.loads(eq.get('params_json') or '{}')
        print(f"  {eq['nume']:20} {len(params)} params stored")


if __name__ == "__main__":
    main()
