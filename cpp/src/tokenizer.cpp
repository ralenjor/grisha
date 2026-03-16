#include "tokenizer.hpp"

#include <sstream>
#include <algorithm>

namespace grisha {

// ============================================================================
// Porter Stemmer Implementation
// ============================================================================

bool PorterStemmer::is_consonant(const std::string& word, size_t i) const {
    if (i >= word.size()) return false;
    char c = word[i];
    if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u') return false;
    if (c == 'y') {
        return i == 0 || !is_consonant(word, i - 1);
    }
    return true;
}

size_t PorterStemmer::measure(const std::string& word) const {
    size_t m = 0;
    size_t i = 0;
    size_t len = word.size();

    // Skip leading consonants
    while (i < len && is_consonant(word, i)) i++;

    while (i < len) {
        // Count vowels
        while (i < len && !is_consonant(word, i)) i++;
        // Count consonants
        if (i < len) {
            m++;
            while (i < len && is_consonant(word, i)) i++;
        }
    }
    return m;
}

bool PorterStemmer::has_vowel(const std::string& word) const {
    for (size_t i = 0; i < word.size(); i++) {
        if (!is_consonant(word, i)) return true;
    }
    return false;
}

bool PorterStemmer::ends_double_consonant(const std::string& word) const {
    size_t len = word.size();
    if (len < 2) return false;
    return word[len-1] == word[len-2] && is_consonant(word, len-1);
}

bool PorterStemmer::ends_cvc(const std::string& word) const {
    size_t len = word.size();
    if (len < 3) return false;
    char last = word[len-1];
    if (last == 'w' || last == 'x' || last == 'y') return false;
    return is_consonant(word, len-1) && !is_consonant(word, len-2) && is_consonant(word, len-3);
}

std::string PorterStemmer::step1a(const std::string& word) const {
    if (word.size() < 2) return word;

    if (word.substr(word.size()-4) == "sses") {
        return word.substr(0, word.size()-2);
    }
    if (word.substr(word.size()-3) == "ies") {
        return word.substr(0, word.size()-2);
    }
    if (word.size() >= 2 && word.substr(word.size()-2) == "ss") {
        return word;
    }
    if (word.back() == 's') {
        return word.substr(0, word.size()-1);
    }
    return word;
}

std::string PorterStemmer::step1b(const std::string& word) const {
    if (word.size() < 3) return word;

    if (word.size() >= 3 && word.substr(word.size()-3) == "eed") {
        std::string stem = word.substr(0, word.size()-3);
        if (measure(stem) > 0) {
            return stem + "ee";
        }
        return word;
    }

    std::string result = word;
    bool found = false;

    if (word.size() >= 2 && word.substr(word.size()-2) == "ed") {
        std::string stem = word.substr(0, word.size()-2);
        if (has_vowel(stem)) {
            result = stem;
            found = true;
        }
    } else if (word.size() >= 3 && word.substr(word.size()-3) == "ing") {
        std::string stem = word.substr(0, word.size()-3);
        if (has_vowel(stem)) {
            result = stem;
            found = true;
        }
    }

    if (found) {
        size_t len = result.size();
        if (len >= 2) {
            std::string last2 = result.substr(len-2);
            if (last2 == "at" || last2 == "bl" || last2 == "iz") {
                return result + "e";
            }
        }
        if (ends_double_consonant(result)) {
            char last = result.back();
            if (last != 'l' && last != 's' && last != 'z') {
                return result.substr(0, result.size()-1);
            }
        }
        if (measure(result) == 1 && ends_cvc(result)) {
            return result + "e";
        }
    }
    return result;
}

std::string PorterStemmer::step1c(const std::string& word) const {
    if (word.size() > 1 && word.back() == 'y') {
        std::string stem = word.substr(0, word.size()-1);
        if (has_vowel(stem)) {
            return stem + "i";
        }
    }
    return word;
}

std::string PorterStemmer::step2(const std::string& word) const {
    if (word.size() < 4) return word;

    static const std::vector<std::pair<std::string, std::string>> suffixes = {
        {"ational", "ate"}, {"tional", "tion"}, {"enci", "ence"},
        {"anci", "ance"}, {"izer", "ize"}, {"abli", "able"},
        {"alli", "al"}, {"entli", "ent"}, {"eli", "e"},
        {"ousli", "ous"}, {"ization", "ize"}, {"ation", "ate"},
        {"ator", "ate"}, {"alism", "al"}, {"iveness", "ive"},
        {"fulness", "ful"}, {"ousness", "ous"}, {"aliti", "al"},
        {"iviti", "ive"}, {"biliti", "ble"}
    };

    for (const auto& [suffix, replacement] : suffixes) {
        if (word.size() > suffix.size() &&
            word.substr(word.size() - suffix.size()) == suffix) {
            std::string stem = word.substr(0, word.size() - suffix.size());
            if (measure(stem) > 0) {
                return stem + replacement;
            }
        }
    }
    return word;
}

std::string PorterStemmer::step3(const std::string& word) const {
    if (word.size() < 4) return word;

    static const std::vector<std::pair<std::string, std::string>> suffixes = {
        {"icate", "ic"}, {"ative", ""}, {"alize", "al"},
        {"iciti", "ic"}, {"ical", "ic"}, {"ful", ""},
        {"ness", ""}
    };

    for (const auto& [suffix, replacement] : suffixes) {
        if (word.size() > suffix.size() &&
            word.substr(word.size() - suffix.size()) == suffix) {
            std::string stem = word.substr(0, word.size() - suffix.size());
            if (measure(stem) > 0) {
                return stem + replacement;
            }
        }
    }
    return word;
}

std::string PorterStemmer::step4(const std::string& word) const {
    if (word.size() < 4) return word;

    static const std::vector<std::string> suffixes = {
        "al", "ance", "ence", "er", "ic", "able", "ible", "ant",
        "ement", "ment", "ent", "ion", "ou", "ism", "ate", "iti",
        "ous", "ive", "ize"
    };

    for (const auto& suffix : suffixes) {
        if (word.size() > suffix.size() &&
            word.substr(word.size() - suffix.size()) == suffix) {
            std::string stem = word.substr(0, word.size() - suffix.size());

            // Special case for "ion"
            if (suffix == "ion" && !stem.empty()) {
                char last = stem.back();
                if (last != 's' && last != 't') continue;
            }

            if (measure(stem) > 1) {
                return stem;
            }
        }
    }
    return word;
}

std::string PorterStemmer::step5(const std::string& word) const {
    if (word.empty()) return word;

    // Step 5a
    if (word.back() == 'e') {
        std::string stem = word.substr(0, word.size()-1);
        size_t m = measure(stem);
        if (m > 1 || (m == 1 && !ends_cvc(stem))) {
            return stem;
        }
    }

    // Step 5b
    std::string result = word;
    if (measure(result) > 1 && ends_double_consonant(result) && result.back() == 'l') {
        return result.substr(0, result.size()-1);
    }

    return result;
}

std::string PorterStemmer::stem(const std::string& word) const {
    if (word.size() < 3) return word;

    std::string result = word;
    result = step1a(result);
    result = step1b(result);
    result = step1c(result);
    result = step2(result);
    result = step3(result);
    result = step4(result);
    result = step5(result);

    return result;
}

// ============================================================================
// Tokenizer Implementation
// ============================================================================

Tokenizer::Tokenizer() {
    init_stopwords();
    init_preserve_words();
}

void Tokenizer::init_stopwords() {
    stopwords_ = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for",
        "from", "has", "he", "in", "is", "it", "its", "of", "on",
        "that", "the", "to", "was", "were", "will", "with", "would",
        "been", "being", "have", "had", "having", "do", "does", "did",
        "but", "if", "or", "because", "until", "while", "this", "these",
        "those", "then", "than", "when", "where", "who", "which", "what",
        "how", "all", "each", "every", "both", "few", "more", "most",
        "other", "some", "such", "no", "nor", "not", "only", "own",
        "same", "so", "can", "just", "should", "now", "also", "may",
        "into", "over", "after", "before", "between", "under", "again",
        "further", "once", "here", "there", "any", "about", "above",
        "below", "up", "down", "out", "off", "through", "during", "very"
    };
}

void Tokenizer::init_preserve_words() {
    // Military terms that should NOT be treated as stopwords
    preserve_words_ = {
        // Basic military terms
        "fire", "range", "unit", "front", "line", "base", "point",
        "force", "forces", "target", "position", "attack", "defense",
        "advance", "withdraw", "flank", "rear", "zone", "sector",
        "area", "objective", "mission", "operation", "command",
        // Weapons and equipment
        "gun", "tank", "armor", "artillery", "mortar", "missile",
        "rocket", "round", "caliber", "munition", "vehicle",
        // Russian military specific
        "btg", "battalion", "brigade", "regiment", "division", "corps",
        "army", "platoon", "squad", "company", "echelon", "maskirovka",
        // Equipment designations
        "bmp", "btr", "msta", "grad", "smerch", "iskander"
    };
}

bool Tokenizer::is_stopword(const std::string& word) const {
    // Never filter out preserved military terms
    if (preserve_words_.count(word)) {
        return false;
    }
    return stopwords_.count(word) > 0;
}

std::string Tokenizer::normalize(const std::string& word) const {
    std::string result;
    result.reserve(word.size());

    for (char c : word) {
        if (std::isalnum(static_cast<unsigned char>(c))) {
            result += std::tolower(static_cast<unsigned char>(c));
        }
    }

    return result;
}

std::vector<std::string> Tokenizer::tokenize(const std::string& text) const {
    std::vector<std::string> tokens;
    std::istringstream iss(text);
    std::string word;

    while (iss >> word) {
        std::string normalized = normalize(word);

        // Skip empty tokens and very short ones
        if (normalized.size() < 2) continue;

        // Skip stopwords (but preserve military terms)
        if (is_stopword(normalized)) continue;

        // Apply stemming
        std::string stemmed = stemmer_.stem(normalized);

        if (!stemmed.empty()) {
            tokens.push_back(stemmed);
        }
    }

    return tokens;
}

std::vector<std::pair<std::string, uint32_t>> Tokenizer::get_term_frequencies(
    const std::string& text) const {

    std::unordered_map<std::string, uint32_t> freq_map;

    auto tokens = tokenize(text);
    for (const auto& token : tokens) {
        freq_map[token]++;
    }

    std::vector<std::pair<std::string, uint32_t>> result;
    result.reserve(freq_map.size());
    for (auto& [term, freq] : freq_map) {
        result.emplace_back(term, freq);
    }

    return result;
}

}  // namespace grisha
