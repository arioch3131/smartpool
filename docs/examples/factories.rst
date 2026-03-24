Factories API
=============

Object factories for different types and use cases.

This section documents the various concrete `ObjectFactory` implementations provided as examples within the `smartpool` project. These factories demonstrate how to integrate `smartpool` with different types of resources.

Basic
------

.. automodule:: factories.basic.bytesio_factory
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: factories.basic.metadata_factory
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: factories.basic.query_result_factory
   :members:
   :undoc-members:
   :show-inheritance:

Database
--------

.. automodule:: factories.database.sqlalchemy_session_factory
   :members:
   :undoc-members:
   :show-inheritance:

Imaging
-------

.. automodule:: factories.imaging.pil_image_factory
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: factories.imaging.pil_thumbnail_factory
   :members:
   :undoc-members:
   :show-inheritance:

Qt
--

.. automodule:: factories.qt.qpixmap_factory
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: factories.qt.qt_thumbnail_factory
   :members:
   :undoc-members:
   :show-inheritance:

Scientific
----------

.. automodule:: factories.scientific.numpyarray_factory
   :members:
   :undoc-members:
   :show-inheritance:

Available Factory Types
-----------------------

The `smartpool` examples include specialized object factories for various use cases:

*   **Basic Data Structures:** Factories for `BytesIO` objects, generic metadata dictionaries, and query result lists.
*   **Database Connections:** Factory for SQLAlchemy session objects.
*   **Image Processing:** Factories for PIL (Pillow) images and thumbnails, and PyQt6 QPixmap objects and thumbnails.
*   **Scientific Computing:** Factory for NumPy arrays.
*   **Custom Factories:** The `ObjectFactory` interface allows users to define their own custom object types.

For creating custom factories, see the :doc:`../developer_guide/factory_guide`.

Examples
--------

.. toctree::
   :maxdepth: 2
   :caption: Basic usage

   basic_usage

.. toctree::
   :maxdepth: 2
   :caption: Advanced Patterns

   advanced_patterns

.. toctree::
   :maxdepth: 2
   :caption: Integrations

   integrations
