# -*- coding: utf-8 -*-
from viur.core.bones import baseBone
from viur.core.bones.bone import ReadFromClientError, ReadFromClientErrorSeverity
import logging
from typing import List, Union


class colorBone(baseBone):
	type = "color"

	def __init__(self, mode="rgb", *args, **kwargs):  # mode rgb/rgba
		baseBone.__init__(self, *args, **kwargs)
		assert mode in {"rgb", "rgba"}
		self.mode = mode

	def fromClient(self, skel: 'SkeletonInstance', name: str, data: dict, prefix=None) -> Union[None, List[ReadFromClientError]]:
		"""
			Reads a value from the client.
			If this value is valid for this bone,
			store this value and return None.
			Otherwise our previous value is
			left unchanged and an error-message
			is returned.

			:param name: Our name in the skeleton
			:type name: str
			:param data: *User-supplied* request-data
			:type data: dict
			:returns: str or None
		"""
		prefixedName = "{}.{}".format(prefix, name) if prefix else name
		if not name in data:
			return [ReadFromClientError(ReadFromClientErrorSeverity.NotSet, prefixedName, "Field not submitted")]
		value = data[name]
		if not value:
			skel[name] = None
			return [ReadFromClientError(ReadFromClientErrorSeverity.Empty, prefixedName, "No value selected")]
		value = value.lower()
		if value.count("#") > 1:
			return [ReadFromClientError(ReadFromClientErrorSeverity.Invalid, prefixedName, "Invalid value entered")]
		for char in value:
			if not char in "#0123456789abcdef":
				return [ReadFromClientError(ReadFromClientErrorSeverity.Invalid, prefixedName, "Invalid value entered")]
		if self.mode == "rgb":
			if len(value) == 3:
				value = "#" + value
			if len(value) == 4:
				value = value[0:2] + value[1] + 2 * value[2] + 2 * value[3]
			if len(value) == 6 or len(value) == 7:
				if len(value) == 6:
					value = "#" + value
			else:
				return [ReadFromClientError(ReadFromClientErrorSeverity.Invalid, prefixedName, "Invalid value entered")]
		if self.mode == "rgba":
			if len(value) == 8 or len(value) == 9:
				if len(value) == 8:
					value = "#" + value
			else:
				return [ReadFromClientError(ReadFromClientErrorSeverity.Invalid, prefixedName, "Invalid value entered")]
		err = self.isInvalid(value)
		if err:
			return [ReadFromClientError(ReadFromClientErrorSeverity.Invalid, prefixedName, err)]
		skel[name] = value
