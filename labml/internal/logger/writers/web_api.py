import json
import ssl
import time
import urllib.request
import urllib.error
import warnings
from typing import Dict, Optional

import numpy as np

from . import Writer as WriteBase
from ..store.indicators import Indicator
from ..store.indicators.numeric import NumericIndicator
from ...lab import lab_singleton

MAX_BUFFER_SIZE = 1024

class Writer(WriteBase):
    url: Optional[str]

    def __init__(self):
        super().__init__()

        self.scalars_cache = []
        self.last_committed = time.time()
        self.indicators = {}
        self.run_uuid = None
        self.name = None
        self.comment = None
        self.hyperparams = None
        conf = lab_singleton().web_api or {}
        self.url = conf.get('url', None)
        self.frequency = conf.get('frequency', 60)
        self.is_verify_connection = conf.get('verify_connection', True)

    @staticmethod
    def _parse_key(key: str):
        return key

    def set_info(self, *,
                 run_uuid: str,
                 name: str,
                 comment: str):
        self.run_uuid = run_uuid
        self.name = name
        self.comment = comment

    def set_hyperparams(self, hyperparams: Dict[str, any]):
        self.hyperparams = hyperparams

    def start(self):
        if self.url is None:
            return

        data = {
            'run_uuid': self.run_uuid,
            'name': self.name,
            'comment': self.comment,
            'params': {}
        }

        if self.hyperparams is not None:
            for k, v in self.hyperparams.items():
                data['params'][k] = v

        self.last_committed = time.time()
        self.send(data)

    def _write_indicator(self, global_step: int, indicator: Indicator):
        if indicator.is_empty():
            return

        if isinstance(indicator, NumericIndicator):
            value = indicator.get_mean()
            key = self._parse_key(indicator.mean_key)
            if key not in self.indicators:
                self.indicators[key] = []

            self.indicators[key].append((global_step, value))

    def write(self, *,
              global_step: int,
              indicators: Dict[str, Indicator]):
        if self.url is None:
            return

        for ind in indicators.values():
            if not ind.is_print:
                continue

            self._write_indicator(global_step, ind)

        t = time.time()
        if t - self.last_committed > self.frequency:
            self.last_committed = t
            self.flush()

    def flush(self):
        if self.url is None:
            return

        data = {}

        for key, value in self.indicators.items():
            value = np.array(value)
            step: np.ndarray = value[:, 0]
            value: np.ndarray = value[:, 1]
            while value.shape[0] > MAX_BUFFER_SIZE:
                if value.shape[0] % 2 == 1:
                    value = np.concatenate((value, value[-1:]))
                    step = np.concatenate((step, step[-1:]))

                n = value.shape[0] // 2
                step = np.mean(step.reshape(n, 2), axis=-1)
                value = np.mean(value.reshape(n, 2), axis=-1)

            data[key] = {
                'step': step.tolist(),
                'value': value.tolist()
            }

        self.indicators = {}

        self.send({
            'run_uuid': self.run_uuid,
            'track': data
        })

    def send(self, data: Dict[str, any]):
        req = urllib.request.Request(self.url)
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        data = json.dumps(data)
        data = data.encode('utf-8')
        req.add_header('Content-Length', str(len(data)))

        try:
            if self.is_verify_connection:
                response = urllib.request.urlopen(req, data)
            else:
                response = urllib.request.urlopen(req, data,
                                                  context=ssl._create_unverified_context())
            content = response.read().decode('utf-8')
            result = json.loads(content)
            if not result['success']:
                warnings.warn(f"WEB API error {result['error']} : {result['message']}")
        except urllib.error.HTTPError as e:
            warnings.warn(f"Failed to send message to WEB API: {e}")
        except urllib.error.URLError as e:
            warnings.warn(f"Failed to connect to WEB API: {e}")
