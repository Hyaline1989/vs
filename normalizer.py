# normalizer.py
# -*- coding: utf-8 -*-
import re

class ObjectNameNormalizer:
    """Нормализует названия объектов для сравнения"""
    
    def normalize(self, name):
        """Приводит название к стандартному виду для сравнения"""
        if not name:
            return ""
        
        # Удаляем эмодзи
        name = self._remove_emoji(name)
        
        # Убираем все символы, кроме букв, цифр, пробелов и дефисов
        name = re.sub(r'[^\w\s\u0400-\u04FF-]', '', name)
        
        # Приводим к нижнему регистру
        name = name.lower().strip()
        
        # Удаляем организационно-правовые формы
        patterns_to_remove = [
            r'ооо\s*', r'зао\s*', r'оао\s*', r'ао\s*',
            r'ип\s*', r'гк\s*', r'пк\s*', r'ооо\s*[«"]?',
            r'llc\s*', r'inc\s*', r'ltd\s*',
        ]
        
        for pattern in patterns_to_remove:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
        # Удаляем кавычки и специальные символы
        name = re.sub(r'[«»"\'.,]', '', name)
        
        # Удаляем лишние пробелы
        name = ' '.join(name.split())
        
        return name
    
    def _remove_emoji(self, text):
        """Удаляет эмодзи из текста"""
        if not text:
            return text
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            u"\U0001F900-\U0001F9FF"
            u"\U0001FA70-\U0001FAFF"
            u"\U00002600-\U000027BF"
            u"\U0001F004-\U0001F0CF"
            u"\U0001F18E-\U0001F1FF"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub('', text).strip()
    
    def normalize_dict(self, data_dict):
        """Нормализует ключи словаря"""
        result = {}
        for key, value in data_dict.items():
            normalized = self.normalize(key)
            if normalized:
                if normalized in result:
                    if isinstance(result[normalized], dict) and isinstance(value, dict):
                        result[normalized]['count'] = result[normalized].get('count', 0) + value.get('count', 0)
                    else:
                        result[normalized] += value
                else:
                    result[normalized] = value
        return result