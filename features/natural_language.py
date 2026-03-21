from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

# Türkçe stop words listesi
turkce_stop_words = [
    "ve", "bir", "bu", "şu", "o", "ile", "de", "da", "ne", "mi", "mı", "ama", "fakat", "çünkü", "gibi", "çok", "az", "daha"
]

def kelime_analizi(metin):
    # Metni tokenize et (kelimelere ayır)
    kelimeler = word_tokenize(metin.lower())  # Küçük harfe çevir ve tokenize et

    # Stop words'leri kaldır
    temiz_kelimeler = [kelime for kelime in kelimeler if kelime not in turkce_stop_words]
 
    return temiz_kelimeler