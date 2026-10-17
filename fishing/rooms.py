"""Đổi phòng có giới hạn khi ghế bị che/không còn chỗ; không đoán phòng nào vắng."""
import random
import cv2
import numpy as np


class RoomSwitcher:
    def __init__(self, travel):
        self.travel = travel
        self.tried = set()

    def is_open(self, image):
        if image.shape != (900, 1600, 3):
            return False
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        # 16 nút xanh cùng lưới; không dùng phần nền ngoài viền popup.
        valid = 0
        for row in range(4):
            for col in range(4):
                x, y = 573 + 150 * col, 285 + 150 * row
                mask = cv2.inRange(hsv[y-12:y+12, x-40:x+40], (35, 100, 80), (85, 255, 255))
                valid += np.mean(mask > 0) > .5
        return valid >= 15

    def choose(self, area):
        choices = list(set(range(5, 16)) - self.tried)
        if not choices or len(self.tried) >= 3:
            raise RuntimeError('Đã thử 3 khu nhưng chưa tìm được ghế trống; dừng để tránh đi vòng liên tục')
        if area=='dock':
            from .dock import DockController
            room=random.choice(choices)
            self.tried.add(room)
            DockController(self.travel.device,self.travel.output/'dock_rooms').change_room(room)
            return room
        image = self.travel.device.screenshot()
        if not self.is_open(image):
            sign = self.travel.world.match(image, 'room_sign')
            if sign is None:
                self.travel.center(area)
                image = self.travel.device.screenshot()
                sign = self.travel.world.match(image, 'room_sign')
            if sign is None:
                raise RuntimeError('Không nhận diện biển KHU để đổi phòng')
            self.travel.tap((sign.center[0], sign.y + 82), 'Mở bảng chọn khu')
            self.travel.wait(self.is_open, 'bảng chọn khu', timeout=20)
        room = random.choice(choices)
        self.tried.add(room)
        self.travel.tap((573 + 150 * (room % 4), 285 + 150 * (room // 4)), f'Đổi sang khu {room}')
        self.travel.wait(lambda a: not self.is_open(a) and
                         self.travel.world.map_name(a, require_menu=False) in ('center', area),
                         'map sau đổi khu', timeout=20)
        self.travel.event('ROOM_CHANGED', room=room)
        return room
