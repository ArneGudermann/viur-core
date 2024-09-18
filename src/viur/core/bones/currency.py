import logging
import locale
from viur.core.bones import NumericBone, ReadFromClientError, ReadFromClientErrorSeverity
from viur.core import current

class CurrencyBone(NumericBone):
    def __init__(self, currency_symbol="€", **kwargs):
        super().__init__(precision=2, **kwargs)
        self.currency_symbol = currency_symbol


    def singleValueUnserialize(self, value):
        """
        Unserializes a single value of this data field from the database.

        :param value: The serialized value to unserialize.
        :return: The unserialized value.
        """
        logging.error(f"{current.language.get()=}")
        if self.currency_symbol:
            locale.setlocale(locale.LC_MONETARY, 'de')
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
        if self.currency_symbol:
            locale.setlocale(locale.LC_ALL, 'de_DE')

            if value:
                raw_numbers = str(value).strip(self.currency_symbol)
                amount = locale.atof(raw_numbers)
                return amount
            else:
                return value
        else:
            pass

    def singleValueFromClient(self, value, skel, bone_name, client_data):
        if self.currency_symbol:
            locale.setlocale(locale.LC_ALL, locale='de_DE')
            if value:
                try:
                    conv = locale.localeconv()
                    raw_numbers = value.strip(conv['currency_symbol'])
                    logging.debug(f"here2 {conv}")
                    amount = locale.atof(raw_numbers)
                    logging.debug(f"{amount=}")
                except ValueError as e:
                    pass
                return amount, None
            else:
                return value, None
        else:
            return self.getEmptyValue(), [
                ReadFromClientError(ReadFromClientErrorSeverity.Invalid, "Will not read a BaseBone fromClient!")]
