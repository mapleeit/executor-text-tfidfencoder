import os
import pickle
from typing import Optional, Iterable, Any, List

from jina import Executor, requests, DocumentArray
from jina.excepts import PretrainedModelFileDoesNotExist

cur_dir = os.path.dirname(os.path.abspath(__file__))


def _batch_generator(data: List[Any], batch_size: int):
    for i in range(0, len(data), batch_size):
        yield data[i: i + batch_size]


class TFIDFTextEncoder(Executor):
    """
    Encode text into tf-idf sparse embeddings

    :param path_vectorizer: path of the pre-trained tfidf sklearn vectorizer
    :param default_batch_size: fallback traversal path in case there is not traversal path sent in the request
    :param default_traversal_path: fallback batch size in case there is not batch size sent in the request
    """

    def __init__(
        self,
        path_vectorizer: str = os.path.join(cur_dir, 'model/tfidf_vectorizer.pickle'),
        default_batch_size: int = 2048,
        default_traversal_path: str = 'r',
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.path_vectorizer = path_vectorizer
        self.default_batch_size = default_batch_size
        self.default_traversal_path = default_traversal_path

        if os.path.exists(self.path_vectorizer):
            self.tfidf_vectorizer = pickle.load(open(self.path_vectorizer, 'rb'))
        else:
            raise PretrainedModelFileDoesNotExist(
                f'{self.path_vectorizer} not found, cannot find a fitted tfidf_vectorizer'
            )

    @requests
    def encode(self, docs: Optional[DocumentArray], parameters: dict, *args, **kwargs):
        """
        Generate the TF-IDF feature vector and store it in `doc.embedding` for each `doc` in `docs`.

        :param docs: documents sent to the encoder. The docs must have `text`.
            By default, the input `text` must be a `list` of `str`.
        """

        if docs:
            document_batches_generator = self._get_input_data_generator(docs, parameters)
            self._create_embeddings(document_batches_generator)


    def _get_input_data_generator(self, docs: DocumentArray, parameters: dict):
        """Create a batch generator to iterate over text in a document (or document chunks)."""

        traversal_path = parameters.get('traversal_path', self.default_traversal_path)
        batch_size = parameters.get('batch_size', self.default_batch_size)

        # traverse thought all documents which have to be processed
        flat_docs = docs.traverse_flat(traversal_path)

        # filter out documents without images
        filtered_docs = DocumentArray([doc for doc in flat_docs if doc.text is not None])

        return _batch_generator(filtered_docs, batch_size)

    def _create_embeddings(self, document_batches_generator: Iterable):
        """Update the documents with the embeddings generated by a tfidf"""

        for document_batch in document_batches_generator:
            iterable_of_texts = [d.text for d in document_batch]
            embedding_matrix = self.tfidf_vectorizer.transform(iterable_of_texts)
            for doc, doc_embedding in zip(document_batch, embedding_matrix):
                doc.embedding = doc_embedding
