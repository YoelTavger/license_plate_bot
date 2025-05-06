import requests
from config import PLATE_RECOGNIZER_TOKEN, REGIONS

class OCRService:
    """
    שירות לזיהוי לוחיות רישוי באמצעות PlateRecognizer API
    """
    
    def __init__(self):
        """אתחול השירות"""
        self.token = PLATE_RECOGNIZER_TOKEN
        self.regions = REGIONS
    
    def recognize_plate(self, image_file):
        """
        זיהוי לוחית רישוי מתמונה
        
        Args:
            image_file: קובץ התמונה (בינארי)
            
        Returns:
            dict: תוצאות הזיהוי או None אם נכשל
        """
        try:
            # שליחת התמונה ל-API
            response = requests.post(
                'https://api.platerecognizer.com/v1/plate-reader/',
                data=dict(regions=self.regions),
                files=dict(upload=image_file),
                headers={'Authorization': f'Token {self.token}'}
            )
            
            # בדיקת תקינות התגובה
            if response.status_code == 200 or response.status_code == 201:  # תגובה תקינה
                result = response.json()
                # print(result)
                return result
            else:
                    return None
        except Exception as e:
            return None
    
    def extract_plate_numbers(self, ocr_result):
        """
        חילוץ מספרי לוחיות רישוי מתוצאות ה-OCR
        
        Args:
            ocr_result: תוצאות ה-OCR מה-API
            
        Returns:
            list: רשימת מספרי לוחיות שזוהו, או רשימה ריקה אם לא זוהו לוחיות
        """
        plates = []
        
        # בדיקה אם יש תוצאות
        if not ocr_result or 'results' not in ocr_result:
            return plates
        
        # עיבוד כל התוצאות
        for result in ocr_result['results']:
            plate_text = result.get('plate', '').replace('-', '').replace(' ', '')
            
            # הוספת הלוחית המלאה
            if plate_text:
                plates.append(plate_text)
            
            # חילוץ קטעים של 3 ספרות
            if len(plate_text) >= 3:
                # לוחיות עם מספר ספרות אי-זוגי (מספר באמצע)
                if len(plate_text) % 2 == 1:
                    mid_index = len(plate_text) // 2
                    middle_three = plate_text[mid_index-1:mid_index+2]
                    plates.append(middle_three)
                
                # לוחיות עם מספר ספרות זוגי (מספר בצדדים)
                else:
                    # שלוש ספרות ראשונות
                    first_three = plate_text[:3]
                    plates.append(first_three)
                    
                    # שלוש ספרות אחרונות
                    last_three = plate_text[-3:]
                    plates.append(last_three)
        
        return plates