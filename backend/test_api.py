import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app

def test_app_creation():
    try:
        app = create_app()
        print("App created successfully")
        
        with app.test_client() as client:
            response = client.get('/api/health')
            print(f"Health check status: {response.status_code}")
            print(f"Health check response: {response.get_json()}")
            
            if response.status_code == 200:
                print("Backend verification passed!")
            else:
                print("Backend verification failed!")
                
    except Exception as e:
        print(f"Error creating app: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_app_creation()
