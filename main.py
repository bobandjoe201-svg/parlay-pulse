import os
import threading
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.utils import platform
from kivy.core.window import Window
from kivy.metrics import dp

# Import our backend calculation module
import hits_engine

# Only apply a fixed window size on desktop computers (Windows/Mac/Linux)
if platform not in ('android', 'ios'):
    Window.size = (450, 750)


class HitsApp(App):
    def build(self):
        self.title = "MLB Hits Engine"
        self.active_tab = "KISS"  # Options: 'KISS', 'ALL', 'SKIPPED'
        self.data_payload = None

        # Main Root Layout
        self.root_layout = BoxLayout(orientation='vertical', spacing=0, padding=0)

        # -----------------------------------------------------
        # 1. HEADER BAR
        # -----------------------------------------------------
        header = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(64),
            padding=[dp(10), dp(6)],
            spacing=dp(10)
        )
        # Dark Retro Header Styling
        with header.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(0.12, 0.14, 0.18, 1)
            self.header_bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=self._update_header_bg, size=self._update_header_bg)

        title_box = BoxLayout(orientation='vertical', spacing=dp(2))
        # Title Row: Text + PNG Image Icons
        title_row = BoxLayout(orientation='horizontal', spacing=dp(4), size_hint_y=None, height=dp(26))

        title_label = Label(
            text="[b]PARLAY PULSE: MLB HITS[/b]",
            markup=True,
            font_size='15sp',
            color=(0.9, 0.9, 0.95, 1),
            size_hint_x=None,
            halign='left',
            valign='middle'
        )
        title_label.bind(texture_size=lambda instance, value: setattr(instance, 'width', value[0]))
        
        # Load PNG images for header icons
        chart_icon = Image(source="emojis/chart.png", size_hint=(None, None), size=(dp(20), dp(20)), pos_hint={'center_y': 0.5})
        baseball_icon = Image(source="emojis/baseball.png", size_hint=(None, None), size=(dp(20), dp(20)), pos_hint={'center_y': 0.5})

        title_row.add_widget(title_label)
        title_row.add_widget(chart_icon)
        title_row.add_widget(baseball_icon)
        
        self.subtitle_label = Label(
            text="Loading daily slate...",
            font_size='11sp',
            color=(0.6, 0.65, 0.7, 1),
            halign='left',
            valign='middle'
        )
        self.subtitle_label.bind(size=self.subtitle_label.setter('text_size'))

        title_box.add_widget(title_row)
        title_box.add_widget(self.subtitle_label)

        refresh_btn = Button(
            text="RELOAD",
            bold=True,
            font_size='11sp',
            size_hint=(None, None),
            size=(dp(64), dp(42)),
            pos_hint={'center_y': 0.5},            
            background_color=(0.2, 0.25, 0.35, 1)
        )
        refresh_btn.bind(on_press=self.fetch_data_thread)

        header.add_widget(title_box)
        header.add_widget(refresh_btn)

        # -----------------------------------------------------
        # 2. FILTER TAB NAVIGATION BAR
        # -----------------------------------------------------
        nav_bar = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(48),
            spacing=dp(4),
            padding=[dp(4), dp(4)]
        )

        def create_tab_btn(text, icon_file, bg_color):
            btn = Button(background_color=bg_color)
            box = BoxLayout(orientation='horizontal', spacing=dp(4), padding=[dp(4), 0])
            icon = Image(source=f"emojis/{icon_file}.png", size_hint=(None, None), size=(dp(18), dp(18)), pos_hint={'center_y': 0.5})
            lbl = Label(text=text, font_size='11sp', bold=True, pos_hint={'center_y': 0.5})
            box.add_widget(icon)
            box.add_widget(lbl)
            btn.add_widget(box)
            btn.bind(pos=lambda instance, value: setattr(box, 'pos', value),
                     size=lambda instance, value: setattr(box, 'size', value))
            return btn

        self.btn_kiss = create_tab_btn("KISS Targets", "target", (0.18, 0.4, 0.6, 1))
        self.btn_kiss.bind(on_press=lambda x: self.switch_tab("KISS"))

        self.btn_all = create_tab_btn("Full Slate", "bar_chart", (0.2, 0.22, 0.28, 1))
        self.btn_all.bind(on_press=lambda x: self.switch_tab("ALL"))

        self.btn_skipped = create_tab_btn("Skipped", "warning", (0.2, 0.22, 0.28, 1))
        self.btn_skipped.bind(on_press=lambda x: self.switch_tab("SKIPPED"))

        nav_bar.add_widget(self.btn_kiss)
        nav_bar.add_widget(self.btn_all)
        nav_bar.add_widget(self.btn_skipped)

        # -----------------------------------------------------
        # 3. SCROLLABLE CONTENT BODY
        # -----------------------------------------------------
        self.scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.cards_container = GridLayout(
            cols=1,
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None
        )
        self.cards_container.bind(minimum_height=self.cards_container.setter('height'))
        self.scroll_view.add_widget(self.cards_container)

        # Assemble Root Layout
        self.root_layout.add_widget(header)
        self.root_layout.add_widget(nav_bar)
        self.root_layout.add_widget(self.scroll_view)

        # Trigger Initial Async Data Load
        self.fetch_data_thread()

        return self.root_layout

    def _update_header_bg(self, instance, value):
        self.header_bg.pos = instance.pos
        self.header_bg.size = instance.size

    # -----------------------------------------------------
    # ASYNC THREADING DATA FETCH
    # -----------------------------------------------------
    def fetch_data_thread(self, instance=None):
        self.subtitle_label.text = "Fetching live statistics..."
        self.cards_container.clear_widgets()
        
        loading_lbl = Label(
            text="[b]Analyzing Daily Slate...[/b]\nExecuting Pitcher & Bullpen Projections",
            markup=True,
            halign='center',
            color=(0.7, 0.7, 0.7, 1),
            size_hint_y=None,
            height=dp(200)
        )
        self.cards_container.add_widget(loading_lbl)
        
        threading.Thread(target=self._data_worker, daemon=True).start()

    def _data_worker(self):
        today_str = datetime.today().strftime('%Y-%m-%d')
        payload = hits_engine.get_projected_hits_payload(today_str)
        Clock.schedule_once(lambda dt: self._on_data_loaded(payload))

    def _on_data_loaded(self, payload):
        self.data_payload = payload
        self.subtitle_label.text = f"Slate Date: {payload['target_date']} | Hits Model v5.0"
        self.render_cards()

    # -----------------------------------------------------
    # TAB NAVIGATION & RENDER LOGIC
    # -----------------------------------------------------
    def switch_tab(self, tab_name):
        self.active_tab = tab_name
        
        # Reset Tab Colors
        self.btn_kiss.background_color = (0.2, 0.22, 0.28, 1)
        self.btn_all.background_color = (0.2, 0.22, 0.28, 1)
        self.btn_skipped.background_color = (0.2, 0.22, 0.28, 1)

        if tab_name == "KISS":
            self.btn_kiss.background_color = (0.18, 0.5, 0.35, 1)
        elif tab_name == "ALL":
            self.btn_all.background_color = (0.18, 0.4, 0.6, 1)
        elif tab_name == "SKIPPED":
            self.btn_skipped.background_color = (0.5, 0.25, 0.2, 1)

        self.render_cards()

    def render_cards(self):
        self.cards_container.clear_widgets()

        if not self.data_payload:
            return

        if self.active_tab == "KISS":
            games = self.data_payload.get('kiss_targets', [])
            if not games:
                self.cards_container.add_widget(Label(
                    text="No games today met all 3 'KISS' parlay criteria.",
                    color=(0.6, 0.6, 0.6, 1),
                    size_hint_y=None,
                    height=dp(100)
                ))
            for game in games:
                self.cards_container.add_widget(self.create_game_card(game, is_kiss=True))

        elif self.active_tab == "ALL":
            games = self.data_payload.get('all_games', [])
            for game in games:
                self.cards_container.add_widget(self.create_game_card(game, is_kiss=False))

        elif self.active_tab == "SKIPPED":
            skipped = self.data_payload.get('disqualified_games', [])
            if not skipped:
                self.cards_container.add_widget(Label(
                    text="All games on today's slate passed starter sample size checks.",
                    color=(0.6, 0.6, 0.6, 1),
                    size_hint_y=None,
                    height=dp(100)
                ))
            for item in skipped:
                self.cards_container.add_widget(self.create_skipped_card(item))

    # -----------------------------------------------------
    # GAME CARD UI GENERATOR
    # -----------------------------------------------------
    def create_game_card(self, game, is_kiss=False):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(160),
            padding=dp(10),
            spacing=dp(6)
        )

        # Card Background Styling
        with card.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(0.14, 0.16, 0.2, 1)  # Standard Dark Slate for all cards
            rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
        card.bind(pos=lambda obj, val: setattr(rect, 'pos', val),
                  size=lambda obj, val: setattr(rect, 'size', val))

        # Row 1: Header (Time + Matchup)
        row1 = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(6))
        
        time_lbl = Label(
            text=f"[b]{game['game_time']} ET[/b]",
            markup=True,
            font_size='11sp',
            color=(0.9, 0.75, 0.3, 1) if is_kiss else (0.6, 0.7, 0.8, 1),
            size_hint_x=None,
            width=dp(70),
            valign='middle'
        )
        time_lbl.bind(size=time_lbl.setter('text_size'))

        # Matchup Container with PNG Icons
        matchup_box = BoxLayout(orientation='horizontal', spacing=dp(4), size_hint_x=1, pos_hint={'center_y': 0.5})
        
        away_icon = Image(source=f"emojis/{game['away_abbr'].lower()}.png", size_hint=(None, None), size=(dp(22), dp(22)), pos_hint={'center_y': 0.5})
        away_lbl = Label(text=f"[b]{game['away_abbr']}[/b]", markup=True, font_size='13sp', size_hint_x=None, width=dp(36), valign='middle')
        at_lbl = Label(text="@", font_size='11sp', color=(0.5, 0.5, 0.5, 1), size_hint_x=None, width=dp(14), valign='middle')
        home_lbl = Label(text=f"[b]{game['home_abbr']}[/b]", markup=True, font_size='13sp', size_hint_x=None, width=dp(36), valign='middle')
        home_icon = Image(source=f"emojis/{game['home_abbr'].lower()}.png", size_hint=(None, None), size=(dp(22), dp(22)), pos_hint={'center_y': 0.5})

        matchup_box.add_widget(away_icon)
        matchup_box.add_widget(away_lbl)
        matchup_box.add_widget(at_lbl)
        matchup_box.add_widget(home_lbl)
        matchup_box.add_widget(home_icon)

        delta_lbl = Label(
            text=f"[b]{game['delta_str']} Edge[/b]",
            markup=True,
            font_size='12sp',
            color=(0.3, 0.9, 0.5, 1) if game['delta'] > 0 else (0.8, 0.4, 0.4, 1),
            size_hint_x=None,
            width=dp(85),
            halign='right',
            valign='middle'
        )
        delta_lbl.bind(size=delta_lbl.setter('text_size'))

        row1.add_widget(time_lbl)
        row1.add_widget(matchup_box)
        row1.add_widget(delta_lbl)

        # Row 2: 3-Column Metrics Grid
        row2 = GridLayout(cols=3, size_hint_y=None, height=dp(60), spacing=dp(4))
        
        # Away Proj
        box_away = BoxLayout(orientation='vertical')
        box_away.add_widget(Label(text="Away Proj", font_size='10sp', color=(0.6, 0.6, 0.6, 1)))
        box_away.add_widget(Label(text=f"[b]{game['away_hits']} H[/b]", markup=True, font_size='15sp'))
        
        # Total Game Proj
        box_total = BoxLayout(orientation='vertical')
        box_total.add_widget(Label(text=f"Total (Base {game['baseline_hits']})", font_size='10sp', color=(0.6, 0.6, 0.6, 1)))
        box_total.add_widget(Label(text=f"[b]{game['total_hits']} H[/b]", markup=True, font_size='16sp', color=(1, 0.85, 0.4, 1)))

        # Home Proj
        box_home = BoxLayout(orientation='vertical')
        box_home.add_widget(Label(text="Home Proj", font_size='10sp', color=(0.6, 0.6, 0.6, 1)))
        box_home.add_widget(Label(text=f"[b]{game['home_hits']} H[/b]", markup=True, font_size='15sp'))

        row2.add_widget(box_away)
        row2.add_widget(box_total)
        row2.add_widget(box_home)

        # Row 3: Target Recommendation Badge
        rec_text = game.get('target_rec', 'Neutral Model Slate')
        rec_color = (0.3, 0.85, 0.5, 1) if is_kiss else (0.5, 0.55, 0.65, 1)
        
        rec_lbl = Label(
            text=f"[b]REC:[/b] {rec_text}",
            markup=True,
            font_size='11sp',
            color=rec_color,
            size_hint_y=None,
            height=dp(24),
            halign='left',
            valign='middle'
        )
        rec_lbl.bind(size=rec_lbl.setter('text_size'))

        card.add_widget(row1)
        card.add_widget(row2)
        card.add_widget(rec_lbl)

        return card

    def create_skipped_card(self, item):
        card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(65), padding=dp(8), spacing=dp(2))
        with card.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(0.2, 0.15, 0.15, 1)
            rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(6)])
        card.bind(pos=lambda obj, val: setattr(rect, 'pos', val),
                  size=lambda obj, val: setattr(rect, 'size', val))

        title = Label(text=f"[b]{item['matchup']}[/b]", markup=True, font_size='12sp', color=(0.9, 0.5, 0.5, 1), size_hint_y=None, height=dp(22), valign='middle')
        title.bind(size=title.setter('text_size'))
        reason = Label(text=f"Reason: {item['reason']}", font_size='10sp', color=(0.7, 0.7, 0.7, 1), size_hint_y=None, height=dp(20), valign='middle')
        reason.bind(size=reason.setter('text_size'))

        card.add_widget(title)
        card.add_widget(reason)
        return card


if __name__ == '__main__':
    HitsApp().run()