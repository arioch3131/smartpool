"""
Complete unit tests for QueryResultFactory - 100% coverage.
"""

import sys
from unittest.mock import Mock

from examples.factories import QueryResultFactory

# pylint: disable=attribute-defined-outside-init, too-many-public-methods


class TestQueryResultFactory:
    """Complete tests for QueryResultFactory."""

    def setup_method(self):
        """Setup for each test."""
        self.factory = QueryResultFactory()

    def test_create_empty_list(self):
        """Test creating an empty list."""
        result = self.factory.create()

        assert isinstance(result, list)
        assert not result

    def test_create_multiple_lists(self):
        """Test creating multiple independent lists."""
        list1 = self.factory.create()
        list2 = self.factory.create()
        list3 = self.factory.create()

        # Each creation should return a new list
        assert list1 is not list2
        assert list2 is not list3
        assert list1 is not list3

        # Modifying one list should not affect the others
        list1.append({"test": "data"})
        assert len(list1) == 1
        assert len(list2) == 0
        assert len(list3) == 0

    def test_create_list_type_consistency(self):
        """Test consistency of the created type."""
        for _ in range(5):
            result = self.factory.create()
            assert isinstance(result, list)
            assert hasattr(result, "append")
            assert hasattr(result, "clear")
            assert hasattr(result, "extend")

    def test_reset_empty_list(self):
        """Test resetting an empty list."""
        empty_list = []

        result = self.factory.reset(empty_list)

        assert result is True
        assert len(empty_list) == 0

    def test_reset_populated_list(self):
        """Test resetting a list with data."""
        populated_list = [
            {"id": 1, "name": "John"},
            {"id": 2, "name": "Jane"},
            {"id": 3, "name": "Bob"},
        ]

        # Verify that it contains data
        assert len(populated_list) == 3

        result = self.factory.reset(populated_list)

        assert result is True
        assert not populated_list

    def test_reset_different_list_types(self):
        """Test reset with different content types."""
        # List of dictionaries
        dict_list = [{"key": "value"}, {"another": "item"}]
        result1 = self.factory.reset(dict_list)
        assert result1 is True
        assert len(dict_list) == 0

        # Mixed list
        mixed_list = [{"dict": True}, "string", 123, [1, 2, 3]]
        result2 = self.factory.reset(mixed_list)
        assert result2 is True
        assert len(mixed_list) == 0

        # List of lists
        nested_list = [[1, 2], [3, 4], [5, 6]]
        result3 = self.factory.reset(nested_list)
        assert result3 is True
        assert len(nested_list) == 0

    def test_reset_large_list(self):
        """Test resetting a large list."""
        large_list = [{"id": i, "data": f"item_{i}"} for i in range(1000)]

        assert len(large_list) == 1000

        result = self.factory.reset(large_list)

        assert result is True
        assert len(large_list) == 0

    def test_reset_exception_handling(self):
        """Test exception handling in reset."""
        # Mock that raises an exception on clear()
        mock_list = Mock()
        mock_list.clear.side_effect = AttributeError("Clear failed")

        result = self.factory.reset(mock_list)

        assert result is False
        mock_list.clear.assert_called_once()

    def test_reset_with_invalid_objects(self):
        """Test reset with invalid objects."""
        # String (no clear method)
        result1 = self.factory.reset("not_a_list")
        assert result1 is False

        # None
        result2 = self.factory.reset(None)
        assert result2 is False

        # Integer
        result3 = self.factory.reset(123)
        assert result3 is False

        # Dict (has a clear method but is not a list)
        test_dict = {"key": "value"}
        result4 = self.factory.reset(test_dict)
        assert result4 is True  # Dict.clear() exists and works
        assert not test_dict

    def test_validate_valid_lists(self):
        """Test validation of valid lists."""
        # Empty list
        assert self.factory.validate([]) is True

        # List with data
        assert self.factory.validate([{"id": 1}, {"id": 2}]) is True

        # List with mixed types
        assert self.factory.validate([1, "string", {"dict": True}]) is True

        # List of lists
        assert self.factory.validate([[1, 2], [3, 4]]) is True

    def test_validate_invalid_types(self):
        """Test validation of invalid objects."""
        assert self.factory.validate(None) is False
        assert self.factory.validate("string") is False
        assert self.factory.validate(123) is False
        assert self.factory.validate({"dict": "value"}) is False
        assert self.factory.validate((1, 2, 3)) is False  # Tuple, not a list
        assert self.factory.validate(set([1, 2, 3])) is False

    def test_validate_list_subclasses(self):
        """Test validation with list subclasses."""

        class CustomList(list):
            """Custom list for testing subclasses."""

        custom_list = CustomList([1, 2, 3])
        assert self.factory.validate(custom_list) is True

    def test_validate_edge_cases(self):
        """Test validation of edge cases."""
        # Very large list
        big_list = list(range(10000))
        assert self.factory.validate(big_list) is True

        # List with None inside
        list_with_none = [None, None, None]
        assert self.factory.validate(list_with_none) is True

    def test_get_key_consistency(self):
        """Test key generation consistency."""
        # All calls should return the same key
        keys = [self.factory.get_key() for _ in range(10)]
        expected_key = "query_result_list"

        assert all(key == expected_key for key in keys)

    def test_get_key_independence(self):
        """Test key generation independence."""
        # The key should not depend on the factory's state
        key1 = self.factory.get_key()

        # Perform various operations
        self.factory.create()
        self.factory.reset([1, 2, 3])
        self.factory.validate("test")

        key2 = self.factory.get_key()

        assert key1 == key2 == "query_result_list"

    def test_estimate_size_empty_list(self):
        """Test estimating size of an empty list."""
        empty_list = []

        result = self.factory.estimate_size(empty_list)
        expected = sys.getsizeof([])

        assert result == expected
        assert result > 0

    def test_estimate_size_populated_lists(self):
        """Test estimating size of lists with data."""
        # List with 1 element
        list_1 = [{"id": 1}]
        size_1 = self.factory.estimate_size(list_1)

        # List with 5 elements
        list_5 = [{"id": i} for i in range(5)]
        size_5 = self.factory.estimate_size(list_5)

        # List with 10 elements
        list_10 = [{"id": i} for i in range(10)]
        size_10 = self.factory.estimate_size(list_10)

        # The size should increase with the number of elements
        assert size_1 < size_5 < size_10

        # Check the formula: list_overhead + len(obj) * 100
        list_overhead = sys.getsizeof([])
        assert size_1 == list_overhead + 1 * 100
        assert size_5 == list_overhead + 5 * 100
        assert size_10 == list_overhead + 10 * 100

    def test_estimate_size_calculation_accuracy(self):
        """Test accuracy of the size estimation calculation."""
        # Test with different sizes
        test_cases = [
            ([], sys.getsizeof([]) + 0 * 100),
            ([{}], sys.getsizeof([]) + 1 * 100),
            ([{}, {}], sys.getsizeof([]) + 2 * 100),
            ([{} for _ in range(50)], sys.getsizeof([]) + 50 * 100),
            ([{} for _ in range(50)], sys.getsizeof([]) + 50 * 100),
        ]

        for test_list, expected_size in test_cases:
            actual_size = self.factory.estimate_size(test_list)
            assert actual_size == expected_size

    def test_estimate_size_with_different_content_types(self):
        """Test estimation with different content types."""
        # The calculation uses a fixed estimate of 100 bytes per item
        # regardless of the actual content.

        list_dicts = [{"key": "value"} for _ in range(3)]
        list_strings = ["string1", "string2", "string3"]
        list_ints = [1, 2, 3]
        list_mixed = [{"dict": True}, "string", 123]

        size_dicts = self.factory.estimate_size(list_dicts)
        size_strings = self.factory.estimate_size(list_strings)
        size_ints = self.factory.estimate_size(list_ints)
        size_mixed = self.factory.estimate_size(list_mixed)

        # All should have the same estimated size (3 items * 100 + overhead)
        expected = sys.getsizeof([]) + 3 * 100
        assert size_dicts == expected
        assert size_strings == expected
        assert size_ints == expected
        assert size_mixed == expected

    def test_comprehensive_workflow(self):
        """Test complete workflow."""
        # Create a list
        query_results = self.factory.create()
        assert not query_results

        # Add data (simulating usage)
        query_results.extend(
            [
                {"id": 1, "name": "Alice", "age": 30},
                {"id": 2, "name": "Bob", "age": 25},
                {"id": 3, "name": "Charlie", "age": 35},
            ]
        )
        assert len(query_results) == 3

        # Validate
        is_valid = self.factory.validate(query_results)
        assert is_valid is True

        # Estimate size
        estimated_size = self.factory.estimate_size(query_results)
        expected_size = sys.getsizeof([]) + 3 * 100
        assert estimated_size == expected_size

        # Generate a key
        key = self.factory.get_key()
        assert key == "query_result_list"

        # Reset for reuse
        reset_success = self.factory.reset(query_results)
        assert reset_success is True
        assert not query_results

        # Validate after reset
        is_still_valid = self.factory.validate(query_results)
        assert is_still_valid is True

    def test_factory_immutability(self):
        """Test that the factory is not modified by operations."""
        # Perform various operations and check that the factory remains intact
        original_factory_dict = self.factory.__dict__.copy()

        # Various operations
        self.factory.create()
        self.factory.reset([1, 2, 3])
        self.factory.validate("test")
        self.factory.get_key()
        self.factory.estimate_size([{"test": "data"}])

        # The factory should not have changed
        assert self.factory.__dict__ == original_factory_dict

    def test_multiple_factory_instances(self):
        """Test with multiple factory instances."""
        factory1 = QueryResultFactory()
        factory2 = QueryResultFactory()

        # They should behave identically
        list1 = factory1.create()
        list2 = factory2.create()

        assert isinstance(list1, list) and isinstance(list2, list)
        assert len(list1) == len(list2) == 0
        assert factory1.get_key() == factory2.get_key()

        # Validate cross-factory
        assert factory1.validate(list2) is True
        assert factory2.validate(list1) is True

    def test_realistic_query_result_simulation(self):
        """Test realistic simulation of query results."""
        # Simulate typical SQL query results.
        query_results = self.factory.create()

        # Simulate adding results.
        simulated_results = [
            {
                "user_id": 1,
                "username": "alice",
                "email": "alice@example.com",
                "created_at": "2023-01-01",
            },
            {
                "user_id": 2,
                "username": "bob",
                "email": "bob@example.com",
                "created_at": "2023-01-02",
            },
            {
                "user_id": 3,
                "username": "charlie",
                "email": "charlie@example.com",
                "created_at": "2023-01-03",
            },
        ]

        query_results.extend(simulated_results)

        # Validate the structure
        assert self.factory.validate(query_results) is True
        assert len(query_results) == 3

        # Check the content
        for result in query_results:
            assert isinstance(result, dict)
            assert "user_id" in result
            assert "username" in result
            assert "email" in result

        # Estimate the size
        size = self.factory.estimate_size(query_results)
        assert size > sys.getsizeof([])

        # Clean up for reuse
        assert self.factory.reset(query_results) is True
        assert not query_results
