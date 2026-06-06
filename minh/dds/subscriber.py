"""DDS Subscriber — copied from so_arm_starter for medicine robot communication."""

import asyncio
import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import Any

import rti.asyncio
import rti.connextdds as dds  # noqa: F401


class Subscriber(ABC):
    def __init__(self, topic: str, cls: Any, period: float, domain_id: int, add_to_queue: bool = True):
        self.topic = topic
        self.cls = cls
        self.period = period
        self.domain_id = domain_id
        self.dds_reader = None
        self.stop_event = None
        self.add_to_queue = add_to_queue
        self.data_q: Any = queue.Queue()

    async def read_async(self):
        if self.dds_reader is None:
            p = dds.DomainParticipant(domain_id=self.domain_id)
            self.dds_reader = dds.DataReader(dds.Topic(p, self.topic, self.cls))
        print(f"{self.domain_id}:{self.topic} - Thread is reading data => {self.dds_reader.topic_name}")
        async for data in self.dds_reader.take_data_async():
            if self.add_to_queue:
                self.data_q.put(data)
            else:
                self.consume(data)

    def read_sync(self):
        print(f"{self.domain_id}:{self.topic} - Thread is reading data => {self.dds_reader.topic_name}")
        while self.stop_event and not self.stop_event.is_set():
            try:
                for data in self.dds_reader.take_data():
                    if self.add_to_queue:
                        self.data_q.put(data)
                    else:
                        self.consume(data)
                time.sleep(self.period if self.period > 0 else 1)
            except Exception as e:
                print(f"Error in {self.dds_reader.topic_name}: {e}")
                raise e

    def read_data(self) -> Any:
        if not self.data_q.empty():
            return self.data_q.get()
        return None

    def start(self):
        self.stop()
        self.stop_event = threading.Event()

        if self.dds_reader is None:
            p = dds.DomainParticipant(domain_id=self.domain_id)
            self.dds_reader = dds.DataReader(dds.Topic(p, self.topic, self.cls))

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_in_executor(None, self.read_sync)

    def stop(self):
        if self.stop_event:
            self.stop_event.set()
        self.stop_event = None

    @abstractmethod
    def consume(self, data) -> None:
        pass


class SubscriberWithQueue(Subscriber):
    def __init__(self, domain_id: int, topic: str, cls: Any, period: float):
        super().__init__(topic, cls, period, domain_id, add_to_queue=True)

    def consume(self, data) -> None:
        pass


class SubscriberWithCallback(Subscriber):
    def __init__(self, cb, domain_id: int, topic: str, cls: Any, period: float):
        super().__init__(topic, cls, period, domain_id, add_to_queue=False)
        self.cb = cb

    def consume(self, data) -> None:
        self.cb(self.topic, data)
