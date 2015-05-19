#:after:production/production:section:lista_de_materiales#

Versiones de la lista de material
---------------------------------

.. _production-bom-versions:

Podremos crear distintas versiones de una lista de material seleccionando la
opción *Nueva Versión* de las acciones de una lista de material. En la pantalla
que se nos va abrir deberemos introducir la fecha a partir de la cual será
efectiva la nueva version. Esta información se guardará cómo |start_date|
de la nueva versión y cómo |end_date| de la versión anterior.

En el listado de *Listas de material* sólo veremos aquellas que estan activas.
Utilizando el botón de relacionado podremos ver todas las versiones de una
lista de material y podremos consultar el listado completo de todas las
versiones desde |menu_bom_versions|.

.. |menu_bom_versions| tryref:: production_bom_versions.menu_version_list/complete_name
.. |start_date| field:: production.bom/start_date
.. |end_date| field:: production.bom/end_date
