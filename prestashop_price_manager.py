#!/usr/bin/env python3
"""
PrestaShop Price Manager
========================
Interface graphique pour mettre à jour les prix PrestaShop depuis un fichier Excel fournisseur.

Fonctionnalités:
- Import fichier Excel avec références fournisseur et prix d'achat
- Filtrage par groupe de produits
- Application de marge configurable
- Modification manuelle des prix (double-clic)
- Mise à jour via API PrestaShop
- Génération de fichier SQL (alternative)
- Logs détaillés

Solution de contournement Apache:
  Certains hébergeurs (OVH, o2switch, etc.) bloquent les requêtes HTTP PUT.
  Ce script utilise POST avec ?ps_method=PUT pour contourner cette limitation.

Auteur: BiF Electronic
Licence: MIT
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import pandas as pd
from pathlib import Path
from datetime import datetime
import threading
import configparser
import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET


class PrestaShopAPI:
    """Client API PrestaShop avec contournement du blocage PUT"""
    
    def __init__(self, shop_url, api_key):
        self.api_url = f"{shop_url}/api"
        self.api_key = api_key
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(api_key, '')
        self.session.headers.update({
            'Content-Type': 'application/xml',
            'User-Agent': 'Mozilla/5.0 PrestaShop Price Manager'
        })
    
    def get_product_by_supplier_ref(self, supplier_ref, supplier_id=None):
        """
        Trouve un produit par référence fournisseur.
        
        Args:
            supplier_ref: Référence fournisseur (SKU)
            supplier_id: ID du fournisseur dans PrestaShop (optionnel)
        
        Returns:
            ID du produit ou None si non trouvé
        """
        try:
            # Méthode 1: Chercher par supplier_reference dans products
            r = self.session.get(f"{self.api_url}/products", params={
                'display': '[id,reference,supplier_reference]',
                'filter[supplier_reference]': str(supplier_ref)
            })
            
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                prod = root.find('.//product')
                if prod is not None:
                    return prod.find('id').text
            
            # Méthode 2: Chercher dans product_suppliers (si supplier_id fourni)
            if supplier_id:
                r = self.session.get(f"{self.api_url}/product_suppliers", params={
                    'display': '[id,id_product,product_supplier_reference]',
                    'filter[product_supplier_reference]': str(supplier_ref),
                    'filter[id_supplier]': supplier_id
                })
                
                if r.status_code == 200:
                    root = ET.fromstring(r.content)
                    ps = root.find('.//product_supplier')
                    if ps is not None:
                        return ps.find('id_product').text
                        
        except Exception as e:
            print(f"Erreur recherche {supplier_ref}: {e}")
        return None
    
    def update_product_price(self, product_id, price):
        """
        Met à jour le prix d'un produit.
        
        Utilise POST avec ?ps_method=PUT pour contourner le blocage
        des requêtes PUT par certains hébergeurs (Apache/nginx).
        
        Args:
            product_id: ID du produit PrestaShop
            price: Nouveau prix (HT)
        
        Returns:
            Tuple (success: bool, message: str)
        """
        try:
            # Récupérer le produit actuel
            r = self.session.get(f"{self.api_url}/products/{product_id}")
            if r.status_code != 200:
                return False, f"Produit {product_id} non trouvé"
            
            # Parser et modifier le prix
            root = ET.fromstring(r.content)
            product = root.find('.//product')
            
            # Supprimer les champs en lecture seule qui causent des erreurs
            fields_to_remove = [
                'manufacturer_name', 'quantity', 'position_in_category',
                'type', 'date_add', 'date_upd', 'associations'
            ]
            
            for field in fields_to_remove:
                elem = product.find(field)
                if elem is not None:
                    product.remove(elem)
            
            # Modifier le prix
            price_elem = product.find('price')
            if price_elem is not None:
                price_elem.text = str(price)
            
            # Envoyer via POST avec ps_method=PUT (contourne blocage Apache)
            xml_data = ET.tostring(root, encoding='unicode')
            r = self.session.post(
                f"{self.api_url}/products/{product_id}?ps_method=PUT",
                data=xml_data.encode('utf-8')
            )
            
            if r.status_code == 200:
                return True, "OK"
            else:
                return False, f"Erreur {r.status_code}"
                
        except Exception as e:
            return False, str(e)


class PriceManagerApp:
    """Interface graphique principale"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("💰 PrestaShop Price Manager")
        self.root.geometry("1300x750")
        
        self.df = None
        self.df_filtered = None
        self.marge = tk.DoubleVar(value=12.0)
        self.selected_groups = {}
        self.ps_api = None
        self.product_cache = {}
        self.supplier_id = None
        
        # Colonnes Excel (configurables)
        self.col_sku = 'Internal Article No.'
        self.col_article = 'Article No.'
        self.col_price = 'Price'
        self.col_manufacturer = 'Manufacturer'
        self.col_availability = 'Availability'
        self.col_group = 'Productgroup'
        
        self.load_config()
        self.create_widgets()
    
    def load_config(self):
        """Charge la configuration depuis config.ini"""
        config_path = Path(__file__).parent / 'config.ini'
        if not config_path.exists():
            config_path = Path.home() / 'prestashop_price_manager' / 'config.ini'
        
        if config_path.exists():
            config = configparser.ConfigParser()
            config.read(config_path)
            
            # PrestaShop
            shop_url = config.get('prestashop', 'shop_url', fallback='')
            api_key = config.get('prestashop', 'api_key', fallback='')
            self.supplier_id = config.get('prestashop', 'supplier_id', fallback=None)
            
            if shop_url and api_key:
                self.ps_api = PrestaShopAPI(shop_url, api_key)
            
            # Marge par défaut
            default_margin = config.getfloat('settings', 'default_margin', fallback=12.0)
            self.marge.set(default_margin)
            
            # Colonnes Excel (optionnel)
            self.col_sku = config.get('excel', 'col_sku', fallback=self.col_sku)
            self.col_article = config.get('excel', 'col_article', fallback=self.col_article)
            self.col_price = config.get('excel', 'col_price', fallback=self.col_price)
            self.col_manufacturer = config.get('excel', 'col_manufacturer', fallback=self.col_manufacturer)
            self.col_availability = config.get('excel', 'col_availability', fallback=self.col_availability)
            self.col_group = config.get('excel', 'col_group', fallback=self.col_group)
    
    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === TOP: Contrôles ===
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(top_frame, text="📂 Charger Excel", 
                   command=self.load_excel).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(top_frame, text="Marge (%):").pack(side=tk.LEFT, padx=(20, 5))
        ttk.Spinbox(top_frame, from_=5, to=50, width=5,
                    textvariable=self.marge).pack(side=tk.LEFT)
        
        ttk.Button(top_frame, text="🔄 Appliquer marge", 
                   command=self.apply_margin).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(top_frame, text="✅ Tout sélectionner", 
                   command=self.select_all_groups).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="❌ Tout désélectionner", 
                   command=self.deselect_all_groups).pack(side=tk.LEFT, padx=5)
        
        # Boutons d'action
        self.sql_btn = ttk.Button(top_frame, text="💾 Générer SQL", 
                   command=self.generate_sql)
        self.sql_btn.pack(side=tk.RIGHT, padx=5)
        
        self.update_btn = ttk.Button(top_frame, text="🚀 Mettre à jour via API", 
                   command=self.update_via_api)
        self.update_btn.pack(side=tk.RIGHT, padx=5)
        
        # Status
        api_status = "✅ API connectée" if self.ps_api else "❌ API non configurée"
        ttk.Label(top_frame, text=api_status).pack(side=tk.RIGHT, padx=10)
        
        self.stats_var = tk.StringVar(value="Aucun fichier chargé")
        ttk.Label(top_frame, textvariable=self.stats_var).pack(side=tk.RIGHT, padx=20)
        
        # === MIDDLE: Deux panneaux ===
        middle_frame = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        middle_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # LEFT: Groupes
        left_frame = ttk.LabelFrame(middle_frame, text="📦 Groupes de produits", padding="5")
        middle_frame.add(left_frame, weight=1)
        
        canvas = tk.Canvas(left_frame, width=280)
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=canvas.yview)
        self.groups_frame = ttk.Frame(canvas)
        
        self.groups_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=self.groups_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # RIGHT: Tableau
        right_frame = ttk.LabelFrame(middle_frame, text="📋 Produits (double-clic pour modifier)", padding="5")
        middle_frame.add(right_frame, weight=3)
        
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tree = ttk.Treeview(tree_frame, columns=(
            'ref', 'article', 'manufacturer', 
            'prix_achat', 'prix_vente', 'dispo', 'group'
        ), show='headings', selectmode='browse')
        
        self.tree.heading('ref', text='SKU Fournisseur')
        self.tree.heading('article', text='Article')
        self.tree.heading('manufacturer', text='Fabricant')
        self.tree.heading('prix_achat', text='Prix Achat €')
        self.tree.heading('prix_vente', text='Prix Vente €')
        self.tree.heading('dispo', text='Dispo')
        self.tree.heading('group', text='Groupe')
        
        self.tree.column('ref', width=100)
        self.tree.column('article', width=150)
        self.tree.column('manufacturer', width=100)
        self.tree.column('prix_achat', width=80)
        self.tree.column('prix_vente', width=80)
        self.tree.column('dispo', width=50)
        self.tree.column('group', width=150)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        self.tree.bind('<Double-1>', self.edit_price)
        
        # === BOTTOM: Progress ===
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.StringVar(value="")
        ttk.Label(bottom_frame, textvariable=self.progress_var).pack(side=tk.LEFT)
        
        self.progress_bar = ttk.Progressbar(bottom_frame, length=300, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, padx=10)
        
        self.file_var = tk.StringVar(value="")
        ttk.Label(bottom_frame, textvariable=self.file_var).pack(side=tk.RIGHT)
    
    def load_excel(self):
        """Charge un fichier Excel fournisseur"""
        filepath = filedialog.askopenfilename(
            title="Sélectionner le fichier Excel",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            self.df = pd.read_excel(filepath)
            self.df = self.df.reset_index(drop=True)
            self.file_var.set(f"📄 {Path(filepath).name}")
            
            # Vérifier les colonnes requises
            required_cols = [self.col_sku, self.col_price]
            missing = [c for c in required_cols if c not in self.df.columns]
            if missing:
                raise ValueError(f"Colonnes manquantes: {missing}")
            
            # Calculer prix de vente
            marge = 1 + (self.marge.get() / 100)
            self.df['Prix_Vente'] = (self.df[self.col_price] * marge).round(3)
            
            self.create_group_checkboxes()
            self.filter_and_display()
            
            with_price = len(self.df[self.df[self.col_price] > 0])
            if self.col_availability in self.df.columns:
                available = len(self.df[self.df[self.col_availability] == 'Available'])
                self.stats_var.set(f"📊 {len(self.df)} produits | {with_price} avec prix | {available} dispos")
            else:
                self.stats_var.set(f"📊 {len(self.df)} produits | {with_price} avec prix")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger le fichier:\n{e}")
    
    def create_group_checkboxes(self):
        """Crée les checkboxes pour les groupes de produits"""
        for widget in self.groups_frame.winfo_children():
            widget.destroy()
        
        self.selected_groups = {}
        
        if self.col_group not in self.df.columns:
            ttk.Label(self.groups_frame, text="Pas de colonne groupe").pack()
            return
        
        groups = self.df.groupby(self.col_group).size().sort_index()
        
        for group, count in groups.items():
            var = tk.BooleanVar(value=True)
            self.selected_groups[group] = var
            
            cb = ttk.Checkbutton(
                self.groups_frame, 
                text=f"{group} ({count})",
                variable=var,
                command=self.filter_and_display
            )
            cb.pack(anchor='w', pady=1)
    
    def select_all_groups(self):
        for var in self.selected_groups.values():
            var.set(True)
        self.filter_and_display()
    
    def deselect_all_groups(self):
        for var in self.selected_groups.values():
            var.set(False)
        self.filter_and_display()
    
    def filter_and_display(self):
        """Filtre et affiche les produits"""
        if self.df is None:
            return
        
        if self.col_group in self.df.columns and self.selected_groups:
            selected = [g for g, var in self.selected_groups.items() if var.get()]
            if selected:
                self.df_filtered = self.df[self.df[self.col_group].isin(selected)].copy()
            else:
                self.df_filtered = pd.DataFrame()
        else:
            self.df_filtered = self.df.copy()
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for idx in self.df_filtered.index:
            row = self.df_filtered.loc[idx]
            
            # Disponibilité
            if self.col_availability in self.df.columns:
                dispo = "🟢" if row[self.col_availability] == 'Available' else "🔴"
            else:
                dispo = "➖"
            
            # Fabricant
            if self.col_manufacturer in self.df.columns:
                manufacturer = row[self.col_manufacturer] if pd.notna(row[self.col_manufacturer]) else ''
            else:
                manufacturer = ''
            
            # Article
            if self.col_article in self.df.columns:
                article = row[self.col_article] if pd.notna(row[self.col_article]) else ''
            else:
                article = ''
            
            # Groupe
            if self.col_group in self.df.columns:
                group = row[self.col_group] if pd.notna(row[self.col_group]) else ''
            else:
                group = ''
            
            self.tree.insert('', 'end', iid=str(idx), values=(
                row[self.col_sku],
                article,
                manufacturer,
                f"{row[self.col_price]:.3f}",
                f"{row['Prix_Vente']:.3f}",
                dispo,
                group
            ))
        
        if self.df_filtered is not None and len(self.df_filtered) > 0:
            with_price = len(self.df_filtered[self.df_filtered[self.col_price] > 0])
            self.stats_var.set(f"📊 {len(self.df_filtered)} sélectionnés | {with_price} avec prix")
    
    def apply_margin(self):
        """Applique la marge à tous les produits"""
        if self.df is None:
            return
        
        marge = 1 + (self.marge.get() / 100)
        self.df['Prix_Vente'] = (self.df[self.col_price] * marge).round(3)
        self.filter_and_display()
        messagebox.showinfo("Info", f"Marge de {self.marge.get():.0f}% appliquée !")
    
    def edit_price(self, event):
        """Édite le prix d'un produit (double-clic)"""
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        
        self.tree.selection_set(item_id)
        
        try:
            idx = int(item_id)
        except ValueError:
            return
        
        if idx not in self.df.index:
            return
        
        values = self.tree.item(item_id, 'values')
        article = values[1]
        prix_achat = values[3]
        current_price = values[4]
        
        new_price = simpledialog.askstring(
            "Modifier le prix",
            f"Article: {article}\nPrix achat: {prix_achat} €\n\nNouveau prix de vente (€):",
            initialvalue=current_price,
            parent=self.root
        )
        
        if new_price is None:
            return
        
        try:
            new_price = float(new_price.replace(',', '.'))
            self.df.at[idx, 'Prix_Vente'] = new_price
            
            new_values = list(values)
            new_values[4] = f"{new_price:.3f}"
            self.tree.item(item_id, values=new_values)
            
        except ValueError:
            messagebox.showerror("Erreur", "Prix invalide !")
    
    def update_via_api(self):
        """Met à jour les prix via l'API PrestaShop"""
        if not self.ps_api:
            messagebox.showerror("Erreur", 
                "API non configurée !\n\n"
                "Créez un fichier config.ini avec:\n"
                "[prestashop]\n"
                "shop_url = https://votre-boutique.com\n"
                "api_key = VOTRE_CLE_API")
            return
        
        if self.df_filtered is None or len(self.df_filtered) == 0:
            messagebox.showwarning("Attention", "Aucun produit sélectionné !")
            return
        
        to_update = self.df_filtered[self.df_filtered[self.col_price] > 0].copy()
        
        if len(to_update) == 0:
            messagebox.showwarning("Attention", "Aucun produit avec prix > 0 !")
            return
        
        if not messagebox.askyesno("Confirmer", 
            f"Mettre à jour {len(to_update)} produits via l'API ?\n\n"
            f"Marge appliquée: {self.marge.get():.0f}%"):
            return
        
        self.update_btn.config(state='disabled')
        self.sql_btn.config(state='disabled')
        
        thread = threading.Thread(target=self._do_update, args=(to_update,))
        thread.start()
    
    def _do_update(self, to_update):
        """Exécute la mise à jour en arrière-plan"""
        total = len(to_update)
        updated = 0
        skipped = 0
        errors = 0
        
        log_lines = []
        log_lines.append(f"=== Mise à jour prix {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
        log_lines.append(f"Produits: {total}, Marge: {self.marge.get():.0f}%\n")
        
        for i, (idx, row) in enumerate(to_update.iterrows()):
            supplier_ref = str(row[self.col_sku])
            prix_vente = row['Prix_Vente']
            
            self.progress_var.set(f"📤 {i+1}/{total}: {supplier_ref}")
            self.progress_bar['value'] = (i + 1) / total * 100
            self.root.update_idletasks()
            
            # Chercher le produit
            if supplier_ref in self.product_cache:
                product_id = self.product_cache[supplier_ref]
            else:
                product_id = self.ps_api.get_product_by_supplier_ref(
                    supplier_ref, self.supplier_id)
                if product_id:
                    self.product_cache[supplier_ref] = product_id
            
            if not product_id:
                log_lines.append(f"⏭️ {supplier_ref}: Non trouvé dans PrestaShop")
                skipped += 1
                continue
            
            # Mettre à jour le prix
            success, msg = self.ps_api.update_product_price(product_id, prix_vente)
            
            if success:
                log_lines.append(f"✅ {supplier_ref}: {prix_vente:.3f}€")
                updated += 1
            else:
                log_lines.append(f"❌ {supplier_ref}: {msg}")
                errors += 1
        
        # Sauvegarder le log
        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"price_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))
        
        self.update_btn.config(state='normal')
        self.sql_btn.config(state='normal')
        self.progress_var.set(f"✅ Terminé: {updated} mis à jour, {skipped} ignorés, {errors} erreurs")
        
        messagebox.showinfo("Résultat", 
            f"Mise à jour terminée !\n\n"
            f"✅ Mis à jour: {updated}\n"
            f"⏭️ Ignorés: {skipped}\n"
            f"❌ Erreurs: {errors}\n\n"
            f"Log: {log_file.name}")
    
    def generate_sql(self):
        """Génère un fichier SQL pour mise à jour via phpMyAdmin"""
        if self.df_filtered is None or len(self.df_filtered) == 0:
            messagebox.showwarning("Attention", "Aucun produit sélectionné !")
            return
        
        to_update = self.df_filtered[self.df_filtered[self.col_price] > 0].copy()
        
        if len(to_update) == 0:
            messagebox.showwarning("Attention", "Aucun produit avec prix > 0 !")
            return
        
        # Demander le supplier_id si pas configuré
        supplier_id = self.supplier_id
        if not supplier_id:
            supplier_id = simpledialog.askstring(
                "ID Fournisseur",
                "Entrez l'ID du fournisseur dans PrestaShop:",
                parent=self.root
            )
            if not supplier_id:
                return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sql_file = Path(__file__).parent / f'update_prices_{timestamp}.sql'
        
        sql_lines = []
        sql_lines.append(f"-- Mise à jour prix du {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        sql_lines.append(f"-- Marge appliquée: {self.marge.get():.0f}%")
        sql_lines.append(f"-- Produits: {len(to_update)}")
        sql_lines.append(f"-- Fournisseur ID: {supplier_id}")
        sql_lines.append("")
        
        for idx in to_update.index:
            row = self.df.loc[idx]
            supplier_ref = str(row[self.col_sku])
            prix_vente = row['Prix_Vente']
            
            sql = f"""UPDATE ps_product p
JOIN ps_product_supplier ps ON p.id_product = ps.id_product
SET p.price = {prix_vente:.3f}
WHERE ps.product_supplier_reference = '{supplier_ref}' AND ps.id_supplier = {supplier_id};"""
            sql_lines.append(sql)
        
        sql_lines.append("")
        sql_lines.append("-- Synchroniser ps_product_shop")
        sql_lines.append(f"""UPDATE ps_product_shop psh
JOIN ps_product p ON psh.id_product = p.id_product
JOIN ps_product_supplier ps ON p.id_product = ps.id_product
SET psh.price = p.price
WHERE ps.id_supplier = {supplier_id};""")
        
        with open(sql_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(sql_lines))
        
        self.progress_var.set(f"✅ SQL généré: {sql_file.name}")
        
        messagebox.showinfo("Succès", 
            f"✅ SQL généré!\n\n"
            f"📊 Produits: {len(to_update)}\n"
            f"📄 Fichier: {sql_file.name}\n\n"
            f"Importez ce fichier dans phpMyAdmin.")


def main():
    root = tk.Tk()
    app = PriceManagerApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
