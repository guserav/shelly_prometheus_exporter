import argparse
from collections.abc import Callable, Collection
import dataclasses
import prometheus_client
from prometheus_client import Gauge
import requests
import time
from typing import Any


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


def get_or_create_metric(metric_class: Callable, name: str, description: str, extra_labels: Collection=[]) -> None:
    if name not in METRICS:
        METRICS[name] = metric_class(name, description, CommonLabels.get_label_names() + extra_labels)
    return METRICS[name]


def parse_switch(common_labels: CommonLabels, data: dict):
    # TODO ("temperature", "tC")
    # TODO ("aenergy", "total")
    for gauge_name in ["voltage", "current", "apower", ]:
        gauge: Gauge = get_or_create_metric(Gauge, f"shelly_switch_{gauge_name}", f"Shelly switch {gauge_name} gauge")
        gauge.labels(**common_labels.as_dict()).set(data[gauge_name])


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
