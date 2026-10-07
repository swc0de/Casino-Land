"""The application: window, main loop, global keys and shared services."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from pathlib import Path

import pygame

from ..audio.mixer import SoundBank
from ..core.casino import Casino
from ..core.money import dollars
from ..core.save import Profile, load_profile, save_profile
from . import caches, fonts, theme
from .scene import Scene, SceneManager

# Longest simulated step per frame. A stall (window drag, breakpoint) then slows
# animations briefly instead of making them jump.
MAX_DT = 1 / 20


@dataclass
class AppOptions:
    #: Run for this many seconds then exit. Used for launch checks and CI.
    smoke_seconds: float | None = None
    #: Save the final frame here (PNG) before exiting.
    screenshot: Path | None = None
    start_scene: str = "title"
    #: Where the profile lives; ``None`` keeps everything in memory.
    save_path: Path | None = None
    seed: int | None = None
    fullscreen: bool | None = None
    mute: bool = False


class App:
    def __init__(self, options: AppOptions | None = None) -> None:
        self.options = options or AppOptions()
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        caches.clear_all()  # surfaces and fonts from an earlier pygame session are invalid
        self.audio_ok = self._init_audio()

        pygame.display.set_caption("Neon Royale Casino")
        pygame.display.set_icon(self._make_icon())
        self.screen = self._open_window()
        self.clock = pygame.time.Clock()

        self.rng = random.Random(self.options.seed)
        profile = load_profile(self.options.save_path) if self.options.save_path else Profile()
        self.casino = Casino(profile)
        self.settings = profile.settings
        if self.options.fullscreen is not None:
            self.settings.fullscreen = self.options.fullscreen
        if self.settings.fullscreen:
            self._set_fullscreen(True)

        self.sound = SoundBank(self.audio_ok, self.settings, seed=self.options.seed or 7)
        self.scenes = SceneManager()
        self.time = 0.0
        self.frame = 0
        self.running = True

    # -- setup -------------------------------------------------------------------------

    def _init_audio(self) -> bool:
        if self.options.mute:
            return False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
            return True
        except pygame.error:
            return False

    @staticmethod
    def _make_icon() -> pygame.Surface:
        from .render.chips import chip_top

        return chip_top(dollars(25), 64)

    def _open_window(self) -> pygame.Surface:
        flags = pygame.SCALED | pygame.RESIZABLE
        try:
            return pygame.display.set_mode(theme.SIZE, flags, vsync=1)
        except pygame.error:
            # vsync is unavailable on some drivers (and the headless dummy driver).
            return pygame.display.set_mode(theme.SIZE, flags)

    def _set_fullscreen(self, on: bool) -> None:
        if bool(pygame.display.is_fullscreen()) == on:
            return
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error:
            return
        self.settings.fullscreen = on

    # -- services used by scenes -----------------------------------------------------

    def make_scene(self, name: str) -> Scene:
        from .scenes import create_scene

        return create_scene(name, self)

    def go(self, name: str) -> None:
        """Fade to the scene registered as ``name``."""
        self.sound.play("whoosh", 0.6)
        self.scenes.switch(self.make_scene(name))

    def toggle_mute(self) -> None:
        settings = self.settings
        if settings.master_volume > 0:
            self._volume_before_mute = settings.master_volume
            settings.master_volume = 0.0
            message = "Sound off (M)"
        else:
            settings.master_volume = getattr(self, "_volume_before_mute", 0.8) or 0.8
            message = "Sound on"
        self.sound.apply_volumes()
        top = self.scenes.top
        toast = getattr(top, "toast", None)
        if toast is not None:
            toast.show(message)
        self.save()

    @property
    def anim_speed(self) -> float:
        """Multiplier for dealing and payout animations (the "fast animations" setting)."""
        return 1.8 if self.settings.fast_animations else 1.0

    def save(self) -> None:
        if self.options.save_path is not None:
            save_profile(self.casino.sync(), self.options.save_path)

    def quit(self) -> None:
        self.running = False

    # -- main loop -----------------------------------------------------------------------

    def run(self) -> int:
        started = time.perf_counter()
        try:
            if self.scenes.top is None:
                self.scenes.switch(self.make_scene(self.options.start_scene))
            while self.running:
                dt = min(self.clock.tick(theme.FPS) / 1000, MAX_DT)
                for event in pygame.event.get():
                    self._handle_event(event)
                self.time += dt
                self.frame += 1
                self.sound.update()
                self.scenes.update(dt)
                self.scenes.draw(self.screen)
                if self.settings.show_fps:
                    self._draw_fps()
                if self._smoke_done(started):
                    self._finish_smoke()
                    break
                pygame.display.flip()
        finally:
            for scene in reversed(self.scenes.stack):
                scene.shutdown()
            self.save()
            self.sound.stop_all()
            pygame.quit()
        return 0

    def _smoke_done(self, started: float) -> bool:
        seconds = self.options.smoke_seconds
        return seconds is not None and time.perf_counter() - started >= seconds

    def _finish_smoke(self) -> None:
        if self.options.screenshot is not None:
            self.options.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.screen, self.options.screenshot)

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.quit()
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                self._set_fullscreen(not pygame.display.is_fullscreen())
                return
            if event.key == pygame.K_F3:
                self.settings.show_fps = not self.settings.show_fps
                return
            if event.key == pygame.K_m and not event.mod & pygame.KMOD_CTRL:
                self.toggle_mute()
                return
        self.scenes.handle_event(event)

    def _draw_fps(self) -> None:
        fps = self.clock.get_fps()
        ms = self.clock.get_rawtime()
        label = fonts.get("body_bold", 18).render(
            f"{fps:5.1f} FPS  {ms:2d} ms", True, theme.GOLD_LIGHT
        )
        box = label.get_rect(topright=(theme.WIDTH - 8, 6)).inflate(12, 4)
        pygame.draw.rect(self.screen, theme.INK, box, border_radius=4)
        self.screen.blit(label, label.get_rect(center=box.center))
