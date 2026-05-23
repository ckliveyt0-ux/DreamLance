import urllib.request
import json
import sys

def test_endpoints():
    print("Testing local endpoints on port 8000...")
    
    # 1. Test projects.html is served
    try:
        req = urllib.request.urlopen("http://127.0.0.1:8000/projects")
        html_status = req.getcode()
        print(f"[-] /projects route status: {html_status} (SUCCESS)" if html_status == 200 else f"[!] /projects returned: {html_status}")
    except Exception as e:
        print(f"[!] /projects failed: {e}")
        sys.exit(1)

    # 2. Test api/projects-list is served and valid JSON
    try:
        req = urllib.request.urlopen("http://127.0.0.1:8000/api/projects-list")
        api_status = req.getcode()
        payload = req.read().decode('utf-8')
        data = json.loads(payload)
        
        print(f"[-] /api/projects-list status: {api_status} (SUCCESS)")
        print(f"[-] Retrieved {len(data)} total projects from database.")
        
        # Verify categories
        categories = set(p.get('category') for p in data)
        print(f"[-] Categories found: {list(categories)}")
        
        # Verify first item schema
        if len(data) > 0:
            first = data[0]
            print(f"[-] Sample Project: {first.get('title')} ({first.get('id')}) | {first.get('category')} | {first.get('difficulty')}")
            
    except Exception as e:
        print(f"[!] /api/projects-list failed: {e}")
        sys.exit(1)

    print("\nAll local verification tests PASSED successfully!")

if __name__ == '__main__':
    test_endpoints()

