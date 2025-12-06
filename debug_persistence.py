import unittest
from unittest.mock import MagicMock, patch
import json
import os
from src.data.relationships import RelationshipManager

class TestPersistence(unittest.TestCase):
    def setUp(self):
        # Use a temporary file for testing
        self.test_path = "data/test_persistence.json"
        
        # Ensure we start clean
        if os.path.exists(self.test_path):
            os.remove(self.test_path)
            
        # Patch the STORAGE_PATH class attribute
        self.patcher = patch('src.data.relationships.RelationshipManager.STORAGE_PATH', self.test_path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.test_path):
            os.remove(self.test_path)

    @patch('src.data.relationships.genai')
    def test_expand_and_persist(self, mock_genai):
        # 1. Initialize (loads seed, saves empty persistence)
        print("\n--- Init 1 ---")
        rm = RelationshipManager()
        
        # Verify HPE exists from seed but has no competitors
        info = rm.get_info("HPE")
        print(f"HPE (Start): {info}")
        self.assertEqual(info['competitors'], [])
        
        # 2. Mock Gemini Response
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "target": {
                "ticker": "HPE",
                "name": "Hewlett Packard Enterprise", 
                "sector": "Information Technology",
                "industry": "Technology Hardware, Storage & Peripherals"
            },
            "competitors": [
                {"ticker": "DELL", "name": "Dell Technologies", "sector": "Information Technology", "industry": "Technology Hardware, Storage & Peripherals"},
                {"ticker": "CSCO", "name": "Cisco Systems", "sector": "Information Technology", "industry": "Communications Equipment"}
            ]
        })
        mock_model.generate_content.return_value = mock_response
        
        # 3. Expansion
        print("\n--- Expansion ---")
        success = rm.expand_knowledge("HPE")
        self.assertTrue(success)
        
        # Verify in memory
        info_after = rm.get_info("HPE")
        print(f"HPE (After Expansion): {info_after['competitors']}")
        self.assertIn("DELL", info_after['competitors'])
        
        # Verify on disk
        with open(self.test_path, 'r') as f:
            data = json.load(f)
            print(f"File content (HPE comps): {data['HPE']['competitors']}")
            self.assertIn("DELL", data['HPE']['competitors'])
            
        # 4. Simulate Restart
        print("\n--- Restart (Init 2) ---")
        rm2 = RelationshipManager()
        
        info_restart = rm2.get_info("HPE")
        print(f"HPE (After Restart): {info_restart['competitors']}")
        
        # THIS IS THE FAIL CONDITION
        self.assertIn("DELL", info_restart['competitors'])

if __name__ == '__main__':
    unittest.main()
