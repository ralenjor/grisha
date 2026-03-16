#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "tokenizer.hpp"
#include "posting_list.hpp"
#include "bm25_index.hpp"
#include "hybrid_search.hpp"

namespace py = pybind11;

PYBIND11_MODULE(grisha_bm25, m) {
    m.doc() = "Grisha BM25 Hybrid Search Module";

    // ========================================================================
    // BM25Result
    // ========================================================================
    py::class_<grisha::BM25Result>(m, "BM25Result")
        .def(py::init<>())
        .def(py::init<const std::string&, double, uint32_t>(),
             py::arg("doc_id"), py::arg("score"), py::arg("internal_id") = 0)
        .def_readwrite("doc_id", &grisha::BM25Result::doc_id)
        .def_readwrite("score", &grisha::BM25Result::score)
        .def_readwrite("internal_id", &grisha::BM25Result::internal_id)
        .def("__repr__", [](const grisha::BM25Result& r) {
            return "BM25Result(doc_id='" + r.doc_id + "', score=" +
                   std::to_string(r.score) + ")";
        });

    // ========================================================================
    // SemanticResult
    // ========================================================================
    py::class_<grisha::SemanticResult>(m, "SemanticResult")
        .def(py::init<>())
        .def(py::init<const std::string&, double>(),
             py::arg("doc_id"), py::arg("distance"))
        .def_readwrite("doc_id", &grisha::SemanticResult::doc_id)
        .def_readwrite("distance", &grisha::SemanticResult::distance)
        .def("__repr__", [](const grisha::SemanticResult& r) {
            return "SemanticResult(doc_id='" + r.doc_id + "', distance=" +
                   std::to_string(r.distance) + ")";
        });

    // ========================================================================
    // HybridResult
    // ========================================================================
    py::class_<grisha::HybridResult>(m, "HybridResult")
        .def(py::init<>())
        .def_readwrite("doc_id", &grisha::HybridResult::doc_id)
        .def_readwrite("rrf_score", &grisha::HybridResult::rrf_score)
        .def_readwrite("semantic_score", &grisha::HybridResult::semantic_score)
        .def_readwrite("bm25_score", &grisha::HybridResult::bm25_score)
        .def_readwrite("semantic_rank", &grisha::HybridResult::semantic_rank)
        .def_readwrite("bm25_rank", &grisha::HybridResult::bm25_rank)
        .def("__repr__", [](const grisha::HybridResult& r) {
            return "HybridResult(doc_id='" + r.doc_id + "', rrf_score=" +
                   std::to_string(r.rrf_score) + ", semantic_rank=" +
                   std::to_string(r.semantic_rank) + ", bm25_rank=" +
                   std::to_string(r.bm25_rank) + ")";
        });

    // ========================================================================
    // BM25Index
    // ========================================================================
    py::class_<grisha::BM25Index>(m, "BM25Index")
        .def(py::init<double, double>(),
             py::arg("k1") = 1.2, py::arg("b") = 0.75,
             "Create a BM25 index with specified parameters")
        .def("add_document", &grisha::BM25Index::add_document,
             py::arg("external_id"), py::arg("text"),
             "Add a document to the index")
        .def("finalize", &grisha::BM25Index::finalize,
             "Finalize the index after adding all documents")
        .def("search", &grisha::BM25Index::search,
             py::arg("query"), py::arg("top_k") = 10,
             "Search the index and return top-k results")
        .def("save", &grisha::BM25Index::save,
             py::arg("path"),
             "Save the index to disk")
        .def("load", &grisha::BM25Index::load,
             py::arg("path"),
             "Load an index from disk")
        .def("clear", &grisha::BM25Index::clear,
             "Clear the index")
        .def_property_readonly("document_count", &grisha::BM25Index::document_count)
        .def_property_readonly("vocabulary_size", &grisha::BM25Index::vocabulary_size)
        .def_property_readonly("average_doc_length", &grisha::BM25Index::average_doc_length)
        .def_property_readonly("is_finalized", &grisha::BM25Index::is_finalized)
        .def("get_external_id", &grisha::BM25Index::get_external_id,
             py::arg("internal_id"),
             "Get external ID from internal ID");

    // ========================================================================
    // HybridSearch
    // ========================================================================
    py::class_<grisha::HybridSearch>(m, "HybridSearch")
        .def(py::init<double, double, double>(),
             py::arg("rrf_k") = 60.0,
             py::arg("semantic_weight") = 0.5,
             py::arg("bm25_weight") = 0.5,
             "Create a hybrid search instance")
        .def("search", &grisha::HybridSearch::search,
             py::arg("index"), py::arg("query"),
             py::arg("semantic_results"), py::arg("top_k") = 10,
             "Perform hybrid search combining semantic and BM25 results")
        .def("set_rrf_k", &grisha::HybridSearch::set_rrf_k,
             py::arg("k"),
             "Set the RRF k parameter")
        .def("get_rrf_k", &grisha::HybridSearch::get_rrf_k)
        .def("set_weights", &grisha::HybridSearch::set_weights,
             py::arg("semantic_weight"), py::arg("bm25_weight"),
             "Set the weights for semantic and BM25 components")
        .def("get_semantic_weight", &grisha::HybridSearch::get_semantic_weight)
        .def("get_bm25_weight", &grisha::HybridSearch::get_bm25_weight);

    // ========================================================================
    // Convenience function for hybrid search
    // ========================================================================
    m.def("hybrid_search",
        [](grisha::BM25Index& index,
           const std::string& query,
           const std::vector<grisha::SemanticResult>& semantic_results,
           size_t top_k,
           double rrf_k,
           double semantic_weight,
           double bm25_weight) {
            grisha::HybridSearch hs(rrf_k, semantic_weight, bm25_weight);
            return hs.search(index, query, semantic_results, top_k);
        },
        py::arg("index"),
        py::arg("query"),
        py::arg("semantic_results"),
        py::arg("top_k") = 100,
        py::arg("rrf_k") = 60.0,
        py::arg("semantic_weight") = 0.5,
        py::arg("bm25_weight") = 0.5,
        "Perform hybrid search combining BM25 and semantic results using RRF");

    // ========================================================================
    // Tokenizer (for debugging/testing)
    // ========================================================================
    py::class_<grisha::Tokenizer>(m, "Tokenizer")
        .def(py::init<>())
        .def("tokenize", &grisha::Tokenizer::tokenize,
             py::arg("text"),
             "Tokenize text into stemmed tokens")
        .def("is_stopword", &grisha::Tokenizer::is_stopword,
             py::arg("word"),
             "Check if a word is a stopword");

    // ========================================================================
    // Module version
    // ========================================================================
    m.attr("__version__") = "0.1.0";
}
