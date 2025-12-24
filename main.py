import os
import shutil
import sqlite3
import ssl
import tempfile
from datetime import date, datetime
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

try:
    import certifi
except Exception:
    certifi = None

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.modalview import ModalView
from kivy.utils import platform

BASE_DIR = os.path.dirname(__file__)
KV_FILE = os.path.join(BASE_DIR, "app.kv")
DB_NAME = "base.db"
DB_REMOTE_URL = "https://github.com/Valdeci-cpd/aplicativo-kivy/raw/refs/heads/main/base.db"

Clock.max_iteration = 20

def parse_date(s: str):
    if not s:
        return None
    if isinstance(s, date):
        return s
    if isinstance(s, str):
        s = s.strip()
        if "T" in s:
            s = s.split("T", 1)[0]
        if " " in s:
            s = s.split(" ", 1)[0]
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def format_date(s: str) -> str:
    if not s:
        return ""
    if isinstance(s, date):
        return s.strftime("%m/%d/%Y")
    try:
        d = parse_date(s)
        if d:
            return d.strftime("%m/%d/%Y")
    except Exception:
        pass
    return str(s)

def normalize_tipo(value: str) -> str:
    tipo_upper = str(value or "").strip().upper()
    if "FIXO" in tipo_upper:
        return "FIXO"
    if "PROVIS" in tipo_upper:
        return "PROVISÓRIO"
    return tipo_upper

def fetch_url_bytes(url: str, timeout: int = 30) -> bytes:
    context = None
    if certifi:
        context = ssl.create_default_context(cafile=certifi.where())
    if context:
        with urlopen(url, timeout=timeout, context=context) as response:
            return response.read()
    with urlopen(url, timeout=timeout) as response:
        return response.read()

def ensure_db_available() -> str:
    app = App.get_running_app()
    src = os.path.join(BASE_DIR, DB_NAME)

    if platform == "android":
        dst = os.path.join(app.user_data_dir, DB_NAME)
        if not os.path.exists(dst):
            os.makedirs(app.user_data_dir, exist_ok=True)
            shutil.copyfile(src, dst)
        return dst
    return src

class DB:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def list_contracts(self, q: str = ""):
        q = (q or "").strip()
        where = []
        params = []

        if q:
            where.append("""
                (
                    cl.codigo_cliente LIKE ?
                    OR cl.nome_fantasia LIKE ?
                    OR cl.razao_social LIKE ?
                    OR cl.cidade LIKE ?
                    OR cl.supervisor LIKE ?
                    OR cl.vendedor LIKE ?
                    OR cl.pasta LIKE ?
                )
            """)
            like = f"%{q}%"
            params.extend([like, like, like, like, like, like, like])

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        sql = f"""
            SELECT
                c.numero_contrato,
                c.emissao,
                c.vencimento,
                c.tipo,
                cl.codigo_cliente,
                cl.nome_fantasia,
                cl.razao_social,
                cl.cidade,
                cl.vendedor,
                cl.supervisor,
                cl.pasta
            FROM CONTRATO c
            JOIN CLIENTE cl ON cl.codigo_cliente = c.codigo_cliente
            {where_sql}
            ORDER BY cl.codigo_cliente ASC, c.vencimento ASC, c.numero_contrato ASC
            LIMIT 1000
        """

        with self.connect() as con:
            rows = con.execute(sql, params).fetchall()

        clientes = {}
        for r in rows:
            cod = r["codigo_cliente"]
            if cod not in clientes:
                clientes[cod] = {
                    "codigo_cliente": r["codigo_cliente"],
                    "nome_fantasia": r["nome_fantasia"],
                    "razao_social": r["razao_social"],
                    "cidade": r["cidade"],
                    "vendedor": r["vendedor"],
                    "supervisor": r["supervisor"],
                    "pasta": r["pasta"],
                    "contratos": [],
                }
            clientes[cod]["contratos"].append({
                "numero_contrato": r["numero_contrato"],
                "emissao": r["emissao"],
                "vencimento": r["vencimento"],
                "tipo": r["tipo"],
            })

        items = []
        for cliente in clientes.values():
            contratos = cliente["contratos"]
            count = len(contratos)
            items.append({
                "codigo_cliente": cliente["codigo_cliente"],
                "nome_fantasia": cliente["nome_fantasia"],
                "razao_social": cliente["razao_social"],
                "cidade": cliente["cidade"],
                "vendedor": cliente["vendedor"],
                "supervisor": cliente["supervisor"],
                "pasta": cliente["pasta"],
                "qtd_contratos": str(count),
                "contratos": [c["numero_contrato"] for c in contratos],
            })
        return items

    def get_contract_detail(self, numero_contrato: str):
        sql = """
            SELECT
                c.numero_contrato,
                c.emissao,
                c.vencimento,
                c.tipo,
                cl.codigo_cliente,
                cl.nome_fantasia,
                cl.razao_social,
                cl.cidade,
                cl.vendedor,
                cl.supervisor,
                cl.pasta
            FROM CONTRATO c
            JOIN CLIENTE cl ON cl.codigo_cliente = c.codigo_cliente
            WHERE c.numero_contrato = ?
        """
        sql_prod = """
            SELECT id_produto, codigo_produto, descricao, quantidade
            FROM PRODUTO
            WHERE numero_contrato = ?
            ORDER BY descricao ASC
        """
        with self.connect() as con:
            contrato = con.execute(sql, (numero_contrato,)).fetchone()
            produtos = con.execute(sql_prod, (numero_contrato,)).fetchall()

        if not contrato:
            return None

        produtos_list = [{
            "id_produto": p["id_produto"],
            "codigo_produto": p["codigo_produto"],
            "descricao": p["descricao"],
            "quantidade": p["quantidade"],
        } for p in produtos]

        data = dict(contrato)
        data["produtos"] = produtos_list
        return data

    def get_vendedores_unicos(self) -> list:
        sql = "SELECT DISTINCT vendedor FROM CLIENTE ORDER BY vendedor ASC"
        with self.connect() as con:
            rows = con.execute(sql).fetchall()
        return [r["vendedor"] for r in rows if r["vendedor"]]

    def get_pastas_unicas(self) -> list:
        sql = "SELECT DISTINCT pasta FROM CLIENTE ORDER BY pasta ASC"
        with self.connect() as con:
            rows = con.execute(sql).fetchall()
        return [r["pasta"] for r in rows if r["pasta"]]

    def list_contracts_advanced(self, q: str = "", vendedor: str = "", pastas: list = None):
        q = (q or "").strip()
        if pastas is None:
            pastas = []

        where = []
        params = []

        if q:
            where.append("""
                (
                    cl.codigo_cliente LIKE ?
                    OR cl.nome_fantasia LIKE ?
                    OR cl.razao_social LIKE ?
                    OR cl.cidade LIKE ?
                    OR cl.supervisor LIKE ?
                    OR cl.vendedor LIKE ?
                    OR cl.pasta LIKE ?
                )
            """)
            like = f"%{q}%"
            params.extend([like, like, like, like, like, like, like])

        if vendedor:
            where.append("cl.vendedor = ?")
            params.append(vendedor)

        if pastas:
            placeholders = ",".join(["?" for _ in pastas])
            where.append(f"cl.pasta IN ({placeholders})")
            params.extend(pastas)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        sql = f"""
            SELECT
                c.numero_contrato,
                c.emissao,
                c.vencimento,
                c.tipo,
                cl.codigo_cliente,
                cl.nome_fantasia,
                cl.razao_social,
                cl.cidade,
                cl.vendedor,
                cl.supervisor,
                cl.pasta
            FROM CONTRATO c
            JOIN CLIENTE cl ON cl.codigo_cliente = c.codigo_cliente
            {where_sql}
            ORDER BY cl.codigo_cliente ASC, c.vencimento ASC, c.numero_contrato ASC
            LIMIT 1000
        """
        with self.connect() as con:
            rows = con.execute(sql, params).fetchall()

        clientes = {}
        for r in rows:
            cod = r["codigo_cliente"]
            if cod not in clientes:
                clientes[cod] = {
                    "codigo_cliente": r["codigo_cliente"],
                    "nome_fantasia": r["nome_fantasia"],
                    "razao_social": r["razao_social"],
                    "cidade": r["cidade"],
                    "vendedor": r["vendedor"],
                    "supervisor": r["supervisor"],
                    "pasta": r["pasta"],
                    "contratos": [],
                }
            clientes[cod]["contratos"].append({
                "numero_contrato": r["numero_contrato"],
                "emissao": r["emissao"],
                "vencimento": r["vencimento"],
                "tipo": r["tipo"],
            })

        items = []
        for cliente in clientes.values():
            contratos = cliente["contratos"]
            count = len(contratos)
            items.append({
                "codigo_cliente": cliente["codigo_cliente"],
                "nome_fantasia": cliente["nome_fantasia"],
                "razao_social": cliente["razao_social"],
                "cidade": cliente["cidade"],
                "vendedor": cliente["vendedor"],
                "supervisor": cliente["supervisor"],
                "pasta": cliente["pasta"],
                "qtd_contratos": str(count),
                "contratos": [c["numero_contrato"] for c in contratos],
            })
        return items

class CardClientesScreen(Screen):

    search_text = StringProperty("")
    rv_data = ListProperty([])
    filtro_vendedor = StringProperty("")
    filtro_pastas = ListProperty([])

    def on_pre_enter(self, *args):
        # Carrega ao entrar na tela
        Clock.schedule_once(lambda dt: self.refresh(), 0)

    def refresh(self):
        app = App.get_running_app()
        self.rv_data = app.db.list_contracts_advanced(
            q=self.search_text,
            vendedor=self.filtro_vendedor,
            pastas=self.filtro_pastas
        )

    def on_search_text(self, instance, value):
        """Atualiza search_text conforme digitação e pesquisa incremental."""
        new_value = value or ""
        if new_value == self.search_text:
            return
        self.search_text = new_value
        self.refresh()

    def on_search_validate(self, value: str):
        """Executa a busca ao pressionar Enter/OK no teclado."""
        self.search_text = value or ""
        self.refresh()

    def open_advanced_filter(self):
        """Abre o popup de filtro avançado."""
        app = App.get_running_app()
        screen = app.root.get_screen("advanced_filter")
        screen.set_current_filters(self.filtro_vendedor, self.filtro_pastas)
        app.root.current = "advanced_filter"

    def apply_advanced_filter(self, vendedor: str, pastas: list):
        """Aplica os filtros avançados e volta para a lista."""
        self.filtro_vendedor = vendedor
        self.filtro_pastas = pastas
        self.refresh()
        App.get_running_app().root.current = "list"

    def refresh_database(self):
        """Solicita recarga da base e mostra resultado ao usuário."""
        app = App.get_running_app()
        success, message = app.reload_database()
        if success:
            self.refresh()
            self.show_message("Base atualizada", message)
        else:
            self.show_message("Erro ao atualizar", message)

    def open_about(self):
        """Mostra popup com informações do app."""
        message = (
            "Comodato Viewer\n"
            "Versão 1.0\n"
            "Aplicativo para consulta rápida de contratos de comodatos."
        )
        self.show_message("Sobre", message)

    def open_actions_menu(self):
        """Apresenta um menu compacto com as principais acoes."""
        options = [
            ("Filtro", self.open_advanced_filter),
            ("Atualizar base", self.refresh_database),
            ("Sobre", self.open_about),
        ]
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        modal = ModalView(size_hint=(0.75, None), height=dp(240))
        modal.background = ""
        modal.background_color = (0, 0, 0, 0)
        modal.add_widget(box)

        for text, callback in options:
            btn = Button(text=text, size_hint_y=None, height=dp(44))
            btn.bind(on_release=lambda instance, cb=callback: self._trigger_menu_action(modal, cb))
            box.add_widget(btn)

        close_btn = Button(text="Fechar", size_hint_y=None, height=dp(44))
        close_btn.bind(on_release=modal.dismiss)
        box.add_widget(close_btn)
        modal.open()

    def _trigger_menu_action(self, popup, callback):
        popup.dismiss()
        if callback:
            callback()

    def show_message(self, title: str, message: str):
        box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        lbl = Label(text=message, halign="center", valign="middle")
        lbl.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        btn = Button(text="OK", size_hint_y=None, height=dp(40))
        popup = Popup(title=title, content=box, size_hint=(0.8, 0.4))
        btn.bind(on_release=popup.dismiss)
        box.add_widget(lbl)
        box.add_widget(btn)
        popup.open()

    def open_detail(self, codigo_cliente: str):
        app = App.get_running_app()
        # Buscar todos os contratos do cliente
        contratos = None
        for item in self.rv_data:
            if item["codigo_cliente"] == codigo_cliente:
                contratos = item["contratos"]
                cliente_info = item
                break
        if not contratos:
            return
        # Buscar detalhes de todos os contratos e garantir estrutura esperada
        detalhes = []
        for numero_contrato in contratos:
            detail = app.db.get_contract_detail(numero_contrato)
            if detail:
                tipo_display = normalize_tipo(detail.get("tipo", ""))
                if "FIXO" in tipo_display:
                    tipo_color = [0.18, 0.8, 0.44, 1]
                elif "PROVIS" in tipo_display:
                    tipo_color = [0.95, 0.6, 0.07, 1]
                else:
                    tipo_color = [0.5, 0.5, 0.5, 1]
                detalhes.append({
                    "numero_contrato": str(detail.get("numero_contrato", "")),
                    "emissao": format_date(detail.get("emissao", "")),
                    "vencimento": format_date(detail.get("vencimento", "")),
                    "tipo": str(detail.get("tipo", "")),
                    "tipo_label": tipo_display,
                    "tipo_display": tipo_display,
                    "tipo_color": tipo_color,
                })
        # Passar para a tela de detalhes
        app.root.get_screen("detail").set_data(cliente_info, detalhes)
        app.root.current = "detail"

class ContractDetailScreen(Screen):

    codigo_cliente = StringProperty("")
    nome_fantasia = StringProperty("")
    razao_social = StringProperty("")
    cidade = StringProperty("")
    vendedor = StringProperty("")
    supervisor = StringProperty("")
    pasta = StringProperty("")
    contratos_detalhes = ListProperty([])

    def set_data(self, cliente_info: dict, detalhes: list):
        self.codigo_cliente = str(cliente_info.get("codigo_cliente", "") or "")
        self.nome_fantasia = str(cliente_info.get("nome_fantasia", "") or "")
        self.razao_social = str(cliente_info.get("razao_social", "") or "")
        self.cidade = str(cliente_info.get("cidade", "") or "")
        self.vendedor = str(cliente_info.get("vendedor", "") or "")
        self.supervisor = str(cliente_info.get("supervisor", "") or "")
        self.pasta = str(cliente_info.get("pasta", "") or "")
        formatted = []
        for item in detalhes or []:
            data = dict(item)
            data["emissao"] = format_date(data.get("emissao", ""))
            data["vencimento"] = format_date(data.get("vencimento", ""))
            if not data.get("tipo_label"):
                data["tipo_label"] = normalize_tipo(data.get("tipo", ""))
            if not data.get("tipo_display"):
                data["tipo_display"] = normalize_tipo(data.get("tipo_label", data.get("tipo", "")))
            if not data.get("tipo_color"):
                tipo_upper = data.get("tipo_display", data.get("tipo_label", ""))
                if "FIXO" in tipo_upper:
                    data["tipo_color"] = [0.18, 0.8, 0.44, 1]
                elif "PROVIS" in tipo_upper:
                    data["tipo_color"] = [0.95, 0.6, 0.07, 1]
                else:
                    data["tipo_color"] = [0.5, 0.5, 0.5, 1]
            formatted.append(data)
        self.contratos_detalhes = formatted
        rv = self.ids.get("contratos_rv")
        if rv:
            Clock.schedule_once(lambda dt: setattr(rv, "scroll_y", 1), 0)

    def voltar(self):
        App.get_running_app().root.current = "list"

    def open_products(self, numero_contrato: str):
        """Abre a tela de produtos para um contrato específico"""
        app = App.get_running_app()
        # Buscar detalhes do contrato e seus produtos
        detail = app.db.get_contract_detail(numero_contrato)
        if detail:
            app.root.get_screen("products").set_data(detail)
            app.root.current = "products"

class ProductContractScreen(Screen):

    numero_contrato = StringProperty("")
    emissao = StringProperty("")
    vencimento = StringProperty("")
    tipo = StringProperty("")
    codigo_cliente = StringProperty("")
    nome_fantasia = StringProperty("")
    razao_social = StringProperty("")
    produtos = ListProperty([])

    def set_data(self, detail: dict):
        self.numero_contrato = str(detail.get("numero_contrato", "") or "")
        self.emissao = format_date(detail.get("emissao", "") or "")
        self.vencimento = format_date(detail.get("vencimento", "") or "")
        self.tipo = str(detail.get("tipo", "") or "")
        self.codigo_cliente = str(detail.get("codigo_cliente", "") or "")
        self.nome_fantasia = str(detail.get("nome_fantasia", "") or "")
        self.razao_social = str(detail.get("razao_social", "") or "")
        self.produtos = detail.get("produtos", [])

    def voltar(self):
        App.get_running_app().root.current = "detail"

class RootSM(ScreenManager):
    pass

class AdvancedFilterScreen(Screen):
    selected_vendedor = StringProperty("")
    vendedores = ListProperty([])
    pastas = ListProperty([])
    selected_pastas = ListProperty([])

    def on_pre_enter(self, *args):
        self.load_options()

    def load_options(self):
        """Carrega valores únicos do banco."""
        app = App.get_running_app()
        self.vendedores = app.db.get_vendedores_unicos()
        self.pastas = app.db.get_pastas_unicas()

        spinner = self.ids.get("vendedor_spinner")
        if spinner:
            spinner.values = ["Todos"] + self.vendedores
            spinner.text = self.selected_vendedor or "Todos"
        self.populate_pastas()

    def populate_pastas(self):
        container = self.ids.get("pastas_box")
        if not container:
            return
        container.clear_widgets()
        for pasta in self.pastas:
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(40),
                spacing=dp(10),
            )
            cb = CheckBox(active=pasta in self.selected_pastas)
            cb.bind(active=lambda checkbox, value, pasta=pasta: self.on_pasta_toggle(pasta, value))
            lbl = Label(text=pasta, halign="left", valign="middle")
            lbl.bind(size=lambda instance, value: setattr(instance, "text_size", value))
            row.add_widget(cb)
            row.add_widget(lbl)
            container.add_widget(row)

    def on_pasta_toggle(self, pasta: str, is_active: bool):
        current = set(self.selected_pastas)
        if is_active:
            current.add(pasta)
        else:
            current.discard(pasta)
        self.selected_pastas = sorted(current)

    def on_select_vendedor(self, text: str):
        self.selected_vendedor = "" if text in ("", "Todos") else text

    def set_current_filters(self, vendedor: str, pastas: list):
        self.selected_vendedor = vendedor or ""
        self.selected_pastas = list(pastas or [])
        self.load_options()

    def clear_filters(self):
        self.selected_vendedor = ""
        self.selected_pastas = []
        spinner = self.ids.get("vendedor_spinner")
        if spinner:
            spinner.text = "Todos"
        self.populate_pastas()

    def apply_filters(self):
        """Aplica os filtros e retorna para a lista."""
        app = App.get_running_app()
        list_screen = app.root.get_screen("list")
        list_screen.apply_advanced_filter(self.selected_vendedor, self.selected_pastas)

    def voltar(self):
        App.get_running_app().root.current = "list"

class ComodatoApp(App):
    db = ObjectProperty(None)

    def build(self):
        Builder.load_file(KV_FILE)
        db_path = ensure_db_available()
        self.db = DB(db_path)
        return RootSM()

    def reload_database(self):
        """Baixa a base mais recente do repositório e atualiza o arquivo local."""
        dst_dir = self.user_data_dir if platform == "android" else os.path.dirname(__file__)
        os.makedirs(dst_dir, exist_ok=True)
        dst_path = os.path.join(dst_dir, DB_NAME)

        try:
            data = fetch_url_bytes(DB_REMOTE_URL, timeout=30)
        except (URLError, HTTPError, ssl.SSLError) as exc:
            return False, f"Não foi possível acessar a internet.\n{exc}"
        except Exception as exc:
            return False, f"Erro inesperado ao baixar a base.\n{exc}"

        if not data:
            return False, "O download retornou um arquivo vazio."

        fd, tmp_path = tempfile.mkstemp(suffix=".db", dir=dst_dir)
        os.close(fd)
        try:
            with open(tmp_path, "wb") as tmp_file:
                tmp_file.write(data)
            shutil.move(tmp_path, dst_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        self.db = DB(dst_path)
        return True, "A base de dados foi atualizada com sucesso."

if __name__ == "__main__":
    ComodatoApp().run()
