import logging

from . import NumericBone

class CurrencyBone(NumericBone):
    def __init__(self, currency="€", **kwargs):
        super().__init__(precision=2, **kwargs)
        self.currency = currency

    def singleValueUnserialize(self, value):
        """
        Unserializes a single value of this data field from the database.

        :param value: The serialized value to unserialize.
        :return: The unserialized value.
        """
        import locale
        if self.currency:
            locale.setlocale(locale.LC_MONETARY, 'de_DE')
            if value:
                return locale.currency(value, grouping=True)
            else:
                return locale.currency(0, grouping=True)
        else:
            pass
    def singleValueSerialize(self, value, skel: 'SkeletonInstance', name: str, parentIndexed: bool):
        """
        Unserializes a single value of this data field from the database.

        :param value: The serialized value to unserialize.
        :return: The unserialized value.
        """
        import locale
        if self.unit == "currency":
            locale.setlocale(locale.LC_ALL, 'de_DE')

            if value:
                conv = locale.localeconv()
                raw_numbers = value.strip(self.currency)
                logging.debug(f"here2 {conv}")
                amount = locale.atof(raw_numbers)
                logging.debug(f"{amount=}")
                return amount
            else:
                return value
        else:
            pass

    def singleValueFromClient(self, value, skel, bone_name, client_data):
        logging.debug(f"seri {value},unitbone {self.unit}")
        import locale
        if self.unit == "currency":
            locale.setlocale(locale.LC_ALL, 'de_DE')
            logging.debug("here1")
            if value:
                try:
                    conv = locale.localeconv()
                    raw_numbers = value.strip(conv['currency_symbol'])
                    logging.debug(f"here2 {conv}")
                    amount = locale.atof(raw_numbers)
                    logging.debug(f"{amount=}")
                except ValueError as e:
                    pass
                return amount
            else:
                return value
        else:
            pass
