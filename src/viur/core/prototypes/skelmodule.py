from viur.core import Module, db
from viur.core.skeleton import skeletonByKind, Skeleton, SkeletonInstance
import typing as t


SINGLE_ORDER_TYPE = str | tuple[str, db.SortOrder]
"""
Type for exactly one sort order definitions.
"""

ORDER_TYPE = SINGLE_ORDER_TYPE | tuple[SINGLE_ORDER_TYPE] | list[SINGLE_ORDER_TYPE] | dict[str, str | int] | None
"""
Type for sort order definitions (any amount of single order definitions).
"""

DEFAULT_ORDER_TYPE = ORDER_TYPE | t.Callable[[db.Query], ORDER_TYPE]
"""
Type for default sort order definitions.
"""


class SkelModule(Module):
    """
        This is the extended module prototype used by any other ViUR module prototype.
        It a prototype which generally is bound to some database model abstracted by the ViUR skeleton system.
    """

    kindName: str = None
    """
        Name of the datastore kind that is handled by this module.

        This information is used to bind a specific :class:`viur.core.skeleton.Skeleton`-class to this
        prototype. By default, it is automatically determined from the module's class name, so a module named
        `Animal` refers to a Skeleton named `AnimalSkel` and its kindName is `animal`.

        For more information, refer to the function :func:`~_resolveSkelCls`.
    """

    def _resolveSkelCls(self, *args, **kwargs) -> t.Type[Skeleton]:
        """
        Retrieve the generally associated :class:`viur.core.skeleton.Skeleton` that is used by
        the application.

        This is either be defined by the member variable *kindName* or by a Skeleton named like the
        application class in lower-case order.

        If this behavior is not wanted, it can be definitely overridden by defining module-specific
        :func:`~viewSkel`, :func:`~addSkel`, or :func:`~editSkel` functions, or by overriding this
        function in general.

        :return: Returns a Skeleton class that matches the application.
        """
        return skeletonByKind(self.kindName if self.kindName else str(type(self).__name__).lower())

    def baseSkel(self, *args, **kwargs) -> SkeletonInstance:
        """
        Returns an instance of an unmodified base skeleton for this module.

        This function should only be used in cases where a full, unmodified skeleton of the module is required, e.g.
        for administrative or maintenance purposes.

        By default, baseSkel is used by :func:`~viewSkel`, :func:`~addSkel`, and :func:`~editSkel`.
        """
        return self._resolveSkelCls(*args, **kwargs)()

    @classmethod
    def check_for_changes(cls, skel: SkeletonInstance, old_db_entity: db.Entity) -> bool:
        """
        :param skel: SkeletonInstance for the check
        :param old_db_entity: Old db.Entity that are now in the Datastore
        """
        skel.serialize()
        for key, val in skel.dbEntity.items():
            if old_db_entity[key] != val and key != "changedate":
                return True
        return False
