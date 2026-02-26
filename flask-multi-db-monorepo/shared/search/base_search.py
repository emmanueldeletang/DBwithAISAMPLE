from abc import ABC, abstractmethod

class BaseSearch(ABC):
    @abstractmethod
    def keyword_search(self, query: str):
        pass

    @abstractmethod
    def vector_search(self, vector):
        pass

    @abstractmethod
    def hybrid_search(self, query: str, vector):
        pass

    @abstractmethod
    def advanced_search(self, filters: dict):
        pass

    @abstractmethod
    def paginate_results(self, page: int, per_page: int):
        pass

    @abstractmethod
    def sort_results(self, sort_by: str, ascending: bool = True):
        pass