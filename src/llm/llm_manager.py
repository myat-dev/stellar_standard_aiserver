import re
import json
from typing import Tuple, Optional
from src.llm.info_extractor import name_chain, phone_chain, name_purpose_chain, gyosha_name_purpose_chain
from src.helpers.logger import logger

async def extract_name_purpose(user_input: str) -> Tuple[Optional[str], Optional[str]]:
    response = await name_purpose_chain.ainvoke({"response": user_input})

    raw_content = response.content.strip()
    logger.debug(f"抽出されたLLM出力: {raw_content}") 

    try:
        extracted = json.loads(raw_content)

        if isinstance(extracted, list) and len(extracted) == 2:
            name = extracted[0] if extracted[0] not in [None, "null", ""] else None
            purpose = extracted[1] if extracted[1] not in [None, "null", ""] else None
            return name, purpose
        else:
            raise ValueError("Unexpected list structure")

    except Exception as e:
        logger.error(f"LLM Name & Purpose Extraction error: {e}")
        return None, None

async def extract_name(user_input: str) -> Optional[str]:
    """Extract only the name from user input."""
    try:
        result = await name_chain.ainvoke({"response": user_input})
        name = result.content.strip().strip('"').strip("'")
        return None if name.lower() == "null" else name
    except Exception as e:
        logger.error(f"LLM Name Extraction error: {e}")
        return None

async def extract_phone(user_input: str) -> Optional[str]:
    """Extract only the phone number from user input."""
    try:
        result = await phone_chain.ainvoke({"response": user_input})
        phone = result.content.strip().strip('"').strip("'")
        logger.debug(f"抽出されたLLM出力: {phone}")
        if phone.lower() == "null":
            return None
        else:
            is_valid = await is_valid_japanese_phone_number(phone)
            if not is_valid:
                logger.error(f"Invalid phone number format: {phone}")
                return "wrongformat"
            else:
                return phone
    except Exception as e:
        logger.error(f"LLM Phone Extraction error: {e}")
        return None
    
async def extract_gyosha_name_purpose(user_input: str) -> Tuple[Optional[str], Optional[str]]:
    response = await gyosha_name_purpose_chain.ainvoke({"response": user_input})

    raw_content = response.content.strip()
    logger.debug(f"抽出されたLLM出力: {raw_content}") 

    try:
        extracted = json.loads(raw_content)

        if isinstance(extracted, list) and len(extracted) == 2:
            name = extracted[0] if extracted[0] not in [None, "null", ""] else None
            purpose = extracted[1] if extracted[1] not in [None, "null", ""] else None
            return name, purpose
        else:
            raise ValueError("Unexpected list structure")

    except Exception as e:
        logger.error(f"LLM Name & Purpose Extraction error: {e}")
        return None, None
    
async def is_valid_japanese_phone_number(phone: str) -> bool:

    # 数字とハイフン以外の文字が含まれていないかチェック
    if not re.fullmatch(r'[0-9\-]+', phone):
        logger.debug(f"数字とハイフン以外の文字が含まれている: {phone}")
        return False
    
    # ハイフンを除去して、10桁または11桁の数字かチェック
    raw = phone.replace('-', '')
    if not re.fullmatch(r'\d{10,11}', raw):
        logger.debug(f"10桁または11桁ではない: {raw}")  # Debugging output
        return False 
    
    # 日本の携帯・固定電話番号を想定（例：090-1234-5678, 03-1234-5678, 08012345678）
    # 電話番号パターンをまとめて定義 
    # 携帯電話（070, 080, 090）: 11桁
    if re.fullmatch(r'0[789]0\d{8}', raw):
        logger.debug(f"携帯電話（070, 080, 090）: 11桁: {raw}")
        return True

    # IP電話（050）: 11桁
    if re.fullmatch(r'050\d{8}', raw):
        logger.debug(f"IP電話（050）: 11桁: {raw}")
        return True

    # 固定電話（03, 06: 2桁市外局番+8桁, 他: 3-5桁市外局番+残り）
    # ただし、070/080/090で始まる10桁は携帯番号なので除外、0120はフリーダイヤルなので除く
    if len(raw) == 10 and not raw.startswith(('070', '080', '090', '0120')):
        # 03, 06: 2桁市外局番＋8桁
        if re.fullmatch(r'0[36]\d{8}', raw):
            logger.debug(f"03, 06: 2桁市外局番＋8桁: {raw}")
            return True
        
        # 3桁市外局番（例：011, 045, 052, 075, 092, 095, 098）+7桁
        if re.fullmatch(r'0\d{2}\d{7}', raw):
            logger.debug(f"3桁市外局番（例：011, 045, 052, 075, 092, 095, 098）+7桁: {raw}")
            return True
        
        # 4桁市外局番（例：0123, 0994など）+6桁
        if re.fullmatch(r'0\d{3}\d{6}', raw):
            logger.debug(f"4桁市外局番（例：0123, 0994など）+6桁: {raw}")
            return True
        
        # 5桁市外局番（例：09969など）+5桁
        if re.fullmatch(r'0\d{4}\d{5}', raw):
            logger.debug(f"5桁市外局番（例：09969など）+5桁: {raw}")
            return True

    return False

