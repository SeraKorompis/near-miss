"""Map head angles (yaw, pitch) to a product using calibration data.

    clf = ZoneClassifier.load("calibration.json")
    clf.classify(yaw, pitch)  # -> "chocolate" or None (looking at nothing)

Nearest-centroid: each product has a mean (yaw, pitch) learned during
calibration. A pose is assigned to the closest product, unless it is
further than `max_distance` degrees away from all of them.
"""
import json
import math
from pathlib import Path

import numpy as np


class ZoneClassifier:
    def __init__(self, centroids, max_distance=15.0):
        # centroids: {"chocolate": {"yaw": -20.1, "pitch": 3.2, ...}, ...}
        self.centroids = centroids
        self.max_distance = max_distance

    @classmethod
    def load(cls, path="calibration.json"):
        data = json.loads(Path(path).read_text())
        return cls(data["products"], data.get("max_distance", 15.0))

    @classmethod
    def from_samples(cls, samples, max_distance=None):
        """samples: {"chocolate": [(yaw, pitch), ...], ...}"""
        centroids = {}
        for product, pts in samples.items():
            if not pts:
                continue
            arr = np.array(pts)
            centroids[product] = {
                "yaw": round(float(np.median(arr[:, 0])), 2),
                "pitch": round(float(np.median(arr[:, 1])), 2),
                "yaw_std": round(float(arr[:, 0].std()), 2),
                "pitch_std": round(float(arr[:, 1].std()), 2),
                "n_samples": len(pts),
            }
        if max_distance is None:
            max_distance = cls.suggest_max_distance(centroids)
        return cls(centroids, max_distance)

    @staticmethod
    def suggest_max_distance(centroids):
        """Half the gap between the two closest products, clamped to [6, 20] degrees."""
        names = list(centroids)
        gaps = [
            math.dist((centroids[a]["yaw"], centroids[a]["pitch"]),
                      (centroids[b]["yaw"], centroids[b]["pitch"]))
            for i, a in enumerate(names) for b in names[i + 1:]
        ]
        if not gaps:
            return 15.0
        return round(min(20.0, max(6.0, min(gaps) * 0.75)), 1)

    def distances(self, yaw, pitch):
        return {
            p: math.dist((yaw, pitch), (c["yaw"], c["pitch"]))
            for p, c in self.centroids.items()
        }

    def classify(self, yaw, pitch):
        if not self.centroids:
            return None
        d = self.distances(yaw, pitch)
        best = min(d, key=d.get)
        return best if d[best] <= self.max_distance else None

    def save(self, path="calibration.json", **meta):
        data = {"max_distance": self.max_distance, "products": self.centroids, **meta}
        Path(path).write_text(json.dumps(data, indent=2))

    def warnings(self):
        """Products whose centroids are too close to tell apart reliably."""
        out = []
        names = list(self.centroids)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                gap = math.dist((self.centroids[a]["yaw"], self.centroids[a]["pitch"]),
                                (self.centroids[b]["yaw"], self.centroids[b]["pitch"]))
                if gap < 8:
                    out.append(f"'{a}' and '{b}' are only {gap:.1f} deg apart - "
                               "spread products out or move the camera closer")
        return out
