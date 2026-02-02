from viur.core import conf, current, i18n
from viur.core.bones import BooleanBone, RelationalBone, RelationalConsistency, SortIndexBone, SelectBone, StringBone, \
    TextBone
from viur.core.prototypes import List
from viur.core.skeleton import Skeleton

FLUIDPAGE_KINDS = {
    "text": i18n.translate("core.fluidpage.kind.text", "Text"),
    "image": i18n.translate("core.fluidpage.kind.image", "Image"),
    "video": i18n.translate("core.fluidpage.kind.video", "Video"),
}
WIDTH_TYPES = {str(i): f"{i} Spalte(n)" for i in range(1, 12)} | {"fullwidth": "Gesamte Browserbreite"}
HEIGHT_TYPES = {
    "auto": i18n.translate("core.fluidpage.height.auto"),
    "small": i18n.translate("core.fluidpage.height.small"),
    "medium": i18n.translate("core.fluidpage.height.medium"),
    "large": i18n.translate("core.fluidpage.height.large"),
    "100": i18n.translate("core.fluidpage.height.100"),
    "1-1": i18n.translate("core.fluidpage.height.1-1"),
    "16-9": i18n.translate("core.fluidpage.height.16-9"),
    "16-10": i18n.translate("core.fluidpage.height.16-10"),
    "4-3": i18n.translate("core.fluidpage.height.4-3"),
}


class FluidPageSkel(Skeleton):
    kindName = "viur-fluidpage"

    sortindex = SortIndexBone(
        descr="Sortindex",
        readOnly=True
    )
    languages = SelectBone(
        descr="Sprachen",
        values=conf.i18n.available_languages,
        defaultValue=list(conf.i18n.available_languages),
        multiple=True,
        required=True,
    )

    name = StringBone(
        descr="Name",
        required=True,
        searchable=True,
    )

    # Special behavior: Overwrite seo_url from SeoAbstractSkel to be editable!
    seo_url = StringBone(
        descr="SEO-URLs",
        languages=conf.i18n.available_languages,
        required=True,
        params={
            "category": "SEO & Social Media",
        },
    )
    seo_tags = StringBone(
        descr="SEO-Tags",
        searchable=True,
        multiple=True,
        languages=conf.i18n.available_languages,
        params={
            "category": "SEO & Social Media",
        },
    )


class FluidpageContentSkel(Skeleton):
    kindName = "viur-fluidpage-content"
    sortindex = SortIndexBone(
        visible=False
    )

    idname = StringBone(
        descr="ID für Ankerlinks (keine Leerzeichen)",
        searchable=True,
        # languages=conf.i18n.available_languages
    )

    fluidpage = RelationalBone(
        kind="viur-fluidpage",
        descr="Side",
        required=True,
        consistency=RelationalConsistency.PreventDeletion,
    )

    is_active = BooleanBone(
        descr="Active",
        defaultValue=True,
    )

    width = SelectBone(
        descr="Width",
        values=WIDTH_TYPES,
        defaultValue="1"
    )

    height = SelectBone(
        descr="Height",
        values=HEIGHT_TYPES,  # todo in conf ?
        defaultValue="auto"
    )

    smallbottomgap = BooleanBone(
        descr="Small bottom gap",
        defaultValue=False
    )

    kind = SelectBone(
        descr="Type",
        values=FLUIDPAGE_KINDS,
        required=True
    )
    # Content
    headline = StringBone(
        params={
            "visibleIf": """kind=="video" or
                            kind=="text"
                            """},
        descr="Überschrift",
        searchable=True,
        languages=conf.i18n.available_languages
    )

    subline = StringBone(
        params={
            "visibleIf": """kind=="video" or
                            kind=="text"
                            """},
        descr="Unterüberschrift",
        searchable=True,
        languages=conf.i18n.available_languages
    )
    descr = TextBone(
        params={
            "visibleIf": """kind=="text" """},
        descr="Fließtext",
        searchable=True,
        languages=conf.i18n.available_languages
    )


class FluidPage(List):
    kindName = "viur-fluidpage"
    adminInfo = {
        "name": "Fluidpage",
        "handler": "list.fluidpage.fluidpagecontent",

        "preview": "/fluidpagepage/view/{{key}}",
        "filter": {"orderby": "name"},
        "columns": [
            "name",
            "languages",
            "seo_url",
        ],
        "editViews": [
            {
                "name": "Content",
                "module": "fluidpagecontent",
                "context": "fluidpage.dest.key",
                "columns": (
                    "sortindex",
                    "width",
                    "kind",
                    "image",
                    "headline",
                ),
            }
        ],
    }


FluidPage.json = True


class FluidpageContent(List):
    kindName = "viur-fluidpage-content"
    adminInfo = {
        "name": "Fluidpage-Content",
        "icon": "list-ul",
        "handler": "list",
        "columns": ["kind", "headline", "image", "descr"],
        "display": "hidden",
    }

    roles = {
        "admin": "*",
    }

    default_order = "sortindex"

    def listFilter(self, query):
        if fluidpage := (
            current.request.get().kwargs.get("fluidpage") or current.request.get().context.get("fluidpage")):
            query.mergeExternalFilter({"fluidpage.dest.key": fluidpage})

        if self.render.kind == "json.vi" and (superquery := super().listFilter(query)):
            return superquery

        query.filter("is_active", True)
        return query  # public information


FluidpageContent.json = True
