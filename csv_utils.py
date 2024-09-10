import csv

def get_products():
    with open('products.csv','r',encoding='utf-8') as file:
        products = list(csv.DictReader(file))
    return products

if __name__ == '__main__':
    get_products()