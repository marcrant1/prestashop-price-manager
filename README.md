# 💰 PrestaShop Price Manager

Interface graphique Python pour mettre à jour les prix PrestaShop depuis un fichier Excel fournisseur.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PrestaShop](https://img.shields.io/badge/PrestaShop-1.7%20%7C%208.x-pink.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ Fonctionnalités

- 📂 Import de fichiers Excel (prix fournisseur)
- 📦 Filtrage par groupe de produits
- 💹 Application de marge configurable (%)
- ✏️ Modification manuelle des prix (double-clic)
- 🚀 **Mise à jour via API PrestaShop**
- 💾 Génération de fichier SQL (alternative pour phpMyAdmin)
- 📋 Logs détaillés de chaque opération

## 🔧 Solution de contournement Apache

**Problème :** Certains hébergeurs mutualisés (OVH, o2switch, etc.) bloquent les requêtes HTTP `PUT` et `DELETE` pour des raisons de sécurité.

**Solution :** Ce script utilise `POST` avec le paramètre `?ps_method=PUT`, une fonctionnalité native de PrestaShop qui permet de contourner cette limitation.

```python
# Au lieu de :
session.put(f"{api_url}/products/{id}", data=xml)

# On utilise :
session.post(f"{api_url}/products/{id}?ps_method=PUT", data=xml)
```

## 📋 Prérequis

- Python 3.8+
- Accès à l'API Webservice PrestaShop
- Fichier Excel avec références fournisseur et prix

## 🚀 Installation

1. **Cloner le dépôt**
```bash
git clone https://github.com/votre-username/prestashop-price-manager.git
cd prestashop-price-manager
```

2. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

3. **Configurer**
```bash
cp config.ini.example config.ini
# Éditer config.ini avec vos paramètres
```

4. **Lancer**
```bash
python prestashop_price_manager.py
```

## ⚙️ Configuration

Créez un fichier `config.ini` :

```ini
[prestashop]
# URL de votre boutique (sans /api)
shop_url = https://www.votre-boutique.com

# Clé API WebService PrestaShop
# (Paramètres avancés → Webservice → Ajouter une clé)
api_key = VOTRE_CLE_API_ICI

# ID du fournisseur dans PrestaShop (optionnel)
supplier_id = 1234

[settings]
# Marge par défaut en pourcentage
default_margin = 12.0

[excel]
# Noms des colonnes dans votre fichier Excel
# (optionnel - valeurs par défaut ci-dessous)
col_sku = Internal Article No.
col_article = Article No.
col_price = Price
col_manufacturer = Manufacturer
col_availability = Availability
col_group = Productgroup
```

### Configuration API PrestaShop

1. Allez dans **Paramètres avancés → Webservice**
2. Activez le webservice
3. Créez une nouvelle clé API
4. Accordez les permissions :
   - `products` : GET, PUT
   - `product_suppliers` : GET (optionnel)

## 📖 Utilisation

### 1. Charger le fichier Excel

Cliquez sur **📂 Charger Excel** et sélectionnez votre fichier fournisseur.

Le fichier doit contenir au minimum :
- Une colonne SKU/référence fournisseur
- Une colonne prix d'achat

### 2. Filtrer par groupe (optionnel)

Cochez/décochez les groupes de produits à mettre à jour.

### 3. Ajuster la marge

- Modifiez le pourcentage de marge
- Cliquez **🔄 Appliquer marge**

### 4. Modifier des prix individuels (optionnel)

Double-cliquez sur une ligne pour modifier le prix manuellement.

### 5. Mettre à jour

**Option A : Via API (recommandé)**
- Cliquez **🚀 Mettre à jour via API**
- Confirmez
- Suivez la progression

**Option B : Via SQL**
- Cliquez **💾 Générer SQL**
- Importez le fichier `.sql` dans phpMyAdmin

## 📁 Structure du fichier Excel

Exemple de structure supportée :

| Internal Article No. | Article No. | Description | Manufacturer | Price | Availability | Productgroup |
|---------------------|-------------|-------------|--------------|-------|--------------|--------------|
| 601032 | PCW08B | Widget Pro | ACME | 12.50 | Available | Electronics |
| 601033 | PCW09C | Gadget Plus | ACME | 8.75 | Not available | Electronics |

## 📝 Logs

Les logs sont sauvegardés dans le dossier `logs/` :

```
logs/
├── price_update_20240104_143022.log
├── price_update_20240105_091545.log
└── ...
```

Exemple de log :
```
=== Mise à jour prix 2024-01-04 14:30 ===
Produits: 150, Marge: 15%

✅ REF001: achat=12.500€ → vente=14.375€
⏭️ REF002: Non trouvé dans PrestaShop
❌ REF003: Erreur 500
```

## 🐛 Dépannage

### Erreur 405 (Method Not Allowed)

Votre hébergeur bloque les requêtes PUT. Ce script gère automatiquement ce cas avec `POST + ps_method=PUT`.

### Erreur 403 (Forbidden)

- Vérifiez les permissions de votre clé API
- Ajoutez un User-Agent dans les headers (déjà fait dans ce script)

### Produits non trouvés

- Vérifiez que le SKU correspond à `supplier_reference` dans PrestaShop
- Vérifiez l'ID du fournisseur dans la configuration

### Erreur 400 (Bad Request)

L'API retourne une erreur de validation. Consultez le log pour plus de détails.

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amelioration`)
3. Commit (`git commit -am 'Ajout fonctionnalité'`)
4. Push (`git push origin feature/amelioration`)
5. Créer une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙏 Remerciements

- Développé avec l'aide de Claude (Anthropic)
- Inspiré par les besoins réels d'un distributeur B2B

---

*Développé avec l'aide de Claude (Anthropic)*
