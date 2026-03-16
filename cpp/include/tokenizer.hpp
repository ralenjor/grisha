#pragma once

#include <string>
#include <vector>
#include <unordered_set>
#include <unordered_map>
#include <algorithm>
#include <cctype>
#include <cstdint>

namespace grisha {

/**
 * Porter Stemmer implementation for English text.
 * Reduces words to their root form for better BM25 matching.
 */
class PorterStemmer {
public:
    std::string stem(const std::string& word) const;

private:
    bool is_consonant(const std::string& word, size_t i) const;
    size_t measure(const std::string& word) const;
    bool has_vowel(const std::string& word) const;
    bool ends_double_consonant(const std::string& word) const;
    bool ends_cvc(const std::string& word) const;

    std::string step1a(const std::string& word) const;
    std::string step1b(const std::string& word) const;
    std::string step1c(const std::string& word) const;
    std::string step2(const std::string& word) const;
    std::string step3(const std::string& word) const;
    std::string step4(const std::string& word) const;
    std::string step5(const std::string& word) const;
};

/**
 * Text tokenizer with domain-aware stopword filtering.
 * Preserves military terminology that would normally be stopwords.
 */
class Tokenizer {
public:
    Tokenizer();

    /**
     * Tokenize text into lowercase, stemmed tokens.
     * @param text Input text
     * @return Vector of processed tokens
     */
    std::vector<std::string> tokenize(const std::string& text) const;

    /**
     * Get term frequencies for a document.
     * @param text Input text
     * @return Map of term -> frequency
     */
    std::vector<std::pair<std::string, uint32_t>> get_term_frequencies(const std::string& text) const;

    /**
     * Check if a word is a stopword.
     */
    bool is_stopword(const std::string& word) const;

private:
    std::unordered_set<std::string> stopwords_;
    std::unordered_set<std::string> preserve_words_;  // Military terms to keep
    PorterStemmer stemmer_;

    std::string normalize(const std::string& word) const;
    void init_stopwords();
    void init_preserve_words();
};

}  // namespace grisha
