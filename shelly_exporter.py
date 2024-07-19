import argparse
from collections.abc import Callable, Collection
import dataclasses
import prometheus_client
from prometheus_client import Gauge, Enum
import requests
import time
from typing import Any, Union


METRICS = {}

@dataclasses.dataclass()
class CommonLabels():
    name: str
    ip: str
    component_id: int

    @classmethod
    def get_label_names(cls) -> list[str]:
        return [
            "name",
            "ip",
            "component_id",
        ]

    def as_dict(self) -> dict:
        return {x: self[x] for x in self.get_label_names()}

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


def get_or_create_metric(metric_class: Callable, name: str, description: str, extra_labels: Collection=[], **kwargs) -> None:
    if name not in METRICS:
        METRICS[name] = metric_class(name, description, CommonLabels.get_label_names() + extra_labels, **kwargs)
    return METRICS[name]

def lookup(source, path: list[str]):
    if not path:
        return source
    if "." in path:
        path = path.split(".")
    return lookup(source[path[0]], path[1:])

@dataclasses.dataclass
class Metric:
    metric_name: str
    metric_path: list[str] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        if not self.metric_path:
            self.metric_path = [self.metric_name]

    def parse_from_data(self, common_labels: CommonLabels, data: dict, component_name: str) -> None:
        raise NotImplementedError("This shouldn't be called")


@dataclasses.dataclass
class MetricGauge(Metric):
    def parse_from_data(self, common_labels: CommonLabels, data: dict, component_name: str) -> None:
        gauge: Gauge = get_or_create_metric(
                Gauge,
                f"shelly_{component_name}_{self.metric_name}",
                f"Shelly {component_name} {self.metric_name} gauge")
        gauge.labels(**common_labels.as_dict()).set(lookup(data, self.metric_path))


@dataclasses.dataclass
class MetricEnum(Metric):
    states: list[str] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        if not self.states:
            raise ValueError("States needs to be a non empty list")

    def parse_from_data(self, common_labels: CommonLabels, data: dict, component_name: str) -> None:
        enum: Enum = get_or_create_metric(
                Enum,
                f"shelly_{component_name}_{self.metric_name}",
                f"Shelly {component_name} {self.metric_name} Enum",
                states=self.states)
        val = lookup(data, self.metric_path)
        if isinstance(val, bool):
            val = self.states[1 if val else 0]
        enum.labels(**common_labels.as_dict()).state(val)


def parse_switch(common_labels: CommonLabels, data: dict):
    metrics = [
            MetricGauge("voltage"),
            MetricGauge("current"),
            MetricGauge("apower"),
            MetricGauge("temperature", ["temperature", "tC"]),
            MetricGauge("energy_consumed", ["aenergy", "total"]),
            MetricEnum("output", states=["Off", "On"]),
    ]
    for metric in metrics:
        metric.parse_from_data(common_labels, data, "switch")


def collect(ip: str):
    r_device_info = requests.get(f"http://{ip}/rpc/Shelly.GetDeviceInfo")
    r_device_info.raise_for_status()
    name = r_device_info.json()["name"]

    r_status = requests.get(f"http://{ip}/rpc/Shelly.GetStatus")
    r_status.raise_for_status()
    data = r_status.json()

    for key in data:
        if ":" in key:
            c_name, _, c_id = key.partition(":")
            labels = CommonLabels(name=name, ip=ip, component_id=int(c_id))
            if c_name == "switch":
                parse_switch(labels, data[key])
            else:
                raise Exception(f"Can't parse Component: {c_name} in {ip}")
    print(ip)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ip")

    args = parser.parse_args()

    starttime = time.monotonic()
    interval_s = 5
    prometheus_client.start_http_server(8000)

    while True:
        collect(args.ip)
        time.sleep(interval_s - ((time.monotonic() - starttime) % interval_s))


if __name__ == "__main__":
    main()
