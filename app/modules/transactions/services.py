# Standard Imports
from datetime import date, timedelta
from sqlalchemy import and_, func
from pydantic import parse_obj_as
from sqlalchemy_filters import apply_pagination

# Typing Imports
from typing import List, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.query import Query

# Exception Imports
from sqlalchemy_filters.exceptions import InvalidPage
from ...utils.exceptions import ProductsNotFound
from ...utils.exceptions import InvalidStockQuantity
from ...utils.exceptions import NotEnoughStockQuantity
from ...utils.exceptions import ProviderNotFound
from ...utils.exceptions import ItensNotFound
from ...utils.exceptions import InvalidPageItemsNumber
from ...utils.exceptions import InvalidRangeTime

# User Model
from app.modules.users.models import User

# Product Model
from app.modules.products.models import Product

# Provider Model
from app.modules.providers.models import Provider

# Transaction Model and Schemas
from .models import Transaction
from .schemas import TransactionProductsData
from .schemas import IncomingTransactionCreate, OutgoingTransactionCreate
from .schemas import TransactionResponse, TransactionsResponse
from .schemas import TransactionTypeEnum

# Transaction Products Model
from ..transactions_products.models import TransactionProduct

# Pagination Metadata Schema
from ...utils.pagination import make_pagination_metadata


class TransactionService:
    def fetch_one(self, db: Session, id: int) -> TransactionResponse:
        """
        Retrieve one transaction record by id.

        Args:
            db (Session): The database session.
            id (int): The transaction id.

        Raises:
            ItensNotFound: If transaction was found.

        Returns:
            List[TransactionResponse]: A dict with transaction record.
        """
        
        transaction = db.query(Transaction).filter(Transaction.id == id).options(
            joinedload(Transaction.products_transaction).options(
                joinedload(TransactionProduct.product)
            )
        ).first()

        if transaction == None:
            raise ItensNotFound("Transaction was not found")

        return transaction

    def _make_transaction_query_with_filters(self, db: Session, product_name: str = '', provider_name: str = '',
        description: str = '', transaction_type: TransactionTypeEnum = '',
        start_date: date = '', finish_date: date = '') -> Query:
        query = db.query(Transaction)

        # Filter by range datetimes
        if type(start_date) == date and type(finish_date) == date:
            if start_date > finish_date:
                raise InvalidRangeTime("Invalid datetime range")
            else:
                query = query.filter(and_(
                    Transaction.date >= start_date, Transaction.date <= finish_date 
                ))

        # Filter only by start date
        elif type(start_date) == date and finish_date == '':
            query = query.filter(
                Transaction.date >= start_date
            )

        # Filter only by finish date
        elif type(finish_date) == date and start_date == '':
            query = query.filter(
                Transaction.date <= finish_date
            )

        # Filter by provider name
        if provider_name != '':
            query = query.join(Transaction.provider).filter(
                func.lower(Provider.name).contains(provider_name.lower(), autoescape=True)
            )

        # Filter by description
        if description != '':
            query = query.filter(
                func.lower(Transaction.description).contains(description.lower(), autoescape=True)
            )

        # Filter by transaction type (incoming or outcoming)
        if transaction_type != '':
            query = query.filter(
                Transaction.type == transaction_type
            )

        # Filter by product name
        if product_name != '':
            ids = db.query(TransactionProduct).join(TransactionProduct.product).filter(
                func.lower(Product.name).contains(product_name.lower(), autoescape=True)
            ).with_entities(
                TransactionProduct.transaction_id
            ).all()
            ids: List[int] = [id[0] for id in ids]

            query = query.filter(
                Transaction.id.in_(ids)
            )

        return query

    def fetch_all(self, db: Session, product_name: str = '', provider_name: str = '',
        description: str = '', transaction_type: TransactionTypeEnum = '',
        start_date: date = None, finish_date: date = None) -> List[TransactionResponse]:
        """
        Retrieve all transactions records.

        Args:
            db (Session): The database session.
            product_name (str): Product name to filter.
            provider_name (str): Provider name to filter.
            description (str): Description to filter.
            transaction_type (Enum): Transaction type to filter.
            start_date (date): Start date to filter. (YYYY-MM-DD)
            finish_date (date): Finish date to filter. (YYYY-MM-DD)

        Raises:
            ItensNotFound: If no item was found.

        Returns:
            List[TransactionResponse]: A list of dicts with transactions records.
        """
        query = self._make_transaction_query_with_filters(
            db,
            product_name,
            provider_name,
            description,
            transaction_type,
            start_date,
            finish_date
        )
        query_result = query.order_by(Transaction.id).options(
            joinedload(Transaction.products_transaction).options(
                joinedload(TransactionProduct.product)
            )
        ).all()
        transactions = parse_obj_as(List[TransactionResponse], query_result)

        if len(transactions) == 0:
            raise ItensNotFound("No transactions found")

        return transactions

    def fetch_all_with_pagination(self, db: Session, page: int, per_page: int = 20, product_name: str = '',
        provider_name: str = '', description: str = '', transaction_type: TransactionTypeEnum = '',
        start_date: date = None, finish_date: date = None) -> TransactionsResponse:
        """
        Retrieve all transacions records listed by page argument and pagination metadata.

        Args:
            page (int): Page to fetch.
            per_page (int): Amount of transactions per page.
            product_name (str): Product name to filter.
            provider_name (str): Provider name to filter.
            description (str): Description to filter.
            transaction_type (Enum): Transaction type to filter.
            start_date (date): Start date to filter.
            finish_date (date): Finish date to filter.

        Raises:
            InvalidPage: If the page informed is invalid.
            ItensNotFound: If no item was found.
            InvalidPageItemsNumber: Numbers of items per page must be greater than 0.

        Returns:
            TransactionsResponse: A dict with providers records and pagination metadata.
        """
        if page <= 0:
            raise InvalidPage(f"Page number should be positive and greater than zero: {page}")
        if per_page <= 0:
            raise InvalidPageItemsNumber(f"Numbers of items per page must be greater than zero")

        query = self._make_transaction_query_with_filters(
            db,
            product_name,
            provider_name,
            description,
            transaction_type, 
            start_date,
            finish_date
        )
        query = query.order_by(Transaction.id)

        query, pagination = apply_pagination(query, page_number=page, page_size=per_page)
        transactions = parse_obj_as(List[TransactionResponse], query.all())

        if page > pagination.num_pages and pagination.num_pages > 0:
            raise InvalidPage(f"Page number invalid, the total of pages is {pagination.num_pages}: {page}")
        if len(transactions) == 0:
            raise ItensNotFound("No transactions found")

        url_args = {
            "product_name": product_name,
            "provider_name": provider_name,
            "description": description,
            "transaction_type": transaction_type.value if type(transaction_type) == TransactionTypeEnum else '',
            "start_date": start_date,
            "finish_date": finish_date
        }
        pagination_metadata = make_pagination_metadata(
            current_page=page,
            total_pages=pagination.num_pages,
            per_page=per_page,
            total_items=pagination.total_results,
            url_args=url_args
        )
        response = TransactionsResponse(
            pagination_metadata = pagination_metadata,
            records = transactions
        )
        return response

    def _check_provider_existence(self, db: Session, provider_id: int) -> None:
        if provider_id != None:
            provider = db.query(Provider).filter(Provider.id == provider_id).first()
            if provider == None:
                raise ProviderNotFound(provider.name)

    def _sort_by_id_check_and_sum_duplicates(self, payload: List[TransactionProductsData]) -> List[TransactionProductsData]:
        already_added = []
        checked_payload = []

        sorted_payload = sorted(payload, key=lambda v: v.product_id) 
        for value in sorted_payload:
            if value.product_id not in already_added:
                already_added.append(value.product_id)
                checked_payload.append(value)

            else:
                checked_payload[-1].quantity += value.quantity
        
        return checked_payload

    def _check_if_products_payload_is_greater_than_zero(self, payload: List[TransactionProductsData]) -> List[int]:
        products_ids = []
        invalid_stock_ids = []

        for value in payload:
            products_ids.append(value.product_id)

            if value.quantity <= 0:
                invalid_stock_ids.append(value.product_id)

        if len(invalid_stock_ids) > 0:
            raise InvalidStockQuantity(
                str(invalid_stock_ids)
            )

        return products_ids

    def _check_if_products_payload_is_less_than_zero(self, payload: List[TransactionProductsData]) -> List[int]:
        products_ids = []
        invalid_stock_ids = []

        for value in payload:
            products_ids.append(value.product_id)

            if value.quantity >= 0:
                invalid_stock_ids.append(value.product_id)

        if len(invalid_stock_ids) > 0:
            raise InvalidStockQuantity(
                str(invalid_stock_ids)
            )

        return products_ids

    def _check_if_stock_has_enough_outgoing_quantity(self, products_found: List[Product], products_payload: List[TransactionProductsData]) -> None:
        invalid_stock_ids = []

        for p_found, p_payload in zip(products_found, products_payload):
            if p_payload.quantity > p_found.inventory:
                invalid_stock_ids.append(p_found.id)

        if len(invalid_stock_ids) > 0:
            raise NotEnoughStockQuantity(
                str(invalid_stock_ids)
            )

    def _get_products_from_database(self, db: Session, payload_products_id: List[int]) -> List[Product]:
        products_found = db.query(Product).filter(Product.id.in_(payload_products_id)).order_by(Product.id).all()

        raise_error: bool = True
        if len(products_found) == len(payload_products_id):
            raise_error = False

        if raise_error == True:
            for p_found in products_found:
                if p_found.id in payload_products_id:
                    payload_products_id.remove(p_found.id)
            
            raise ItensNotFound(
                str(payload_products_id)
            )

        else:
            return products_found
    
    def _update_products_inventory(self, db: Session, products_found: List[Product], products_payload: List[TransactionProductsData]) -> None:
        dict_products = []
        for p_found, p_payload in zip(products_found, products_payload):
            p_found.inventory = p_found.inventory + p_payload.quantity
            
            dict_products.append(p_found.__dict__)
        
        db.bulk_update_mappings(Product, dict_products)
        db.commit()

    def _update_products_inventory_outgoing(self, db: Session, products_found: List[Product], products_payload: List[TransactionProductsData]) -> None:
        dict_products = []
        for p_found, p_payload in zip(products_found, products_payload):
            p_found.inventory = p_found.inventory - p_payload.quantity
            
            dict_products.append(p_found.__dict__)
        
        db.bulk_update_mappings(Product, dict_products)
        db.commit()
    
    def create(self, db: Session, user: User,
        transaction: Union[IncomingTransactionCreate, 
                           OutgoingTransactionCreate]) -> TransactionResponse:
        """
        Creates a incoming or an outgoing transaction.

        Args:
            db (Session): The database session.
            user (User): The user model.
            transaction (IncomingTransactionCreate or OutgoingTransactionCreate): The incoming or outgoing transaction create model.

        Returns:
            TransactionResponse: The provider response model.
        """
        if len(transaction.products) == 0:
            raise ProductsNotFound("Empty transaction products")

        if transaction.type == TransactionTypeEnum.incoming:
            self._check_provider_existence(db, transaction.provider_id)

            checked_products = self._sort_by_id_check_and_sum_duplicates(transaction.products)
            products_ids = self._check_if_products_payload_is_greater_than_zero(checked_products)

            # Updates products inventory quantity
            products_to_update = self._get_products_from_database(db, products_ids)

            # Creates the record of the current transaction
            transaction_create = Transaction(
                **transaction.dict(exclude_unset=True, exclude={'products'})
            )
            transaction_create.created_by = user.id

            # Creates product transactions records
            products_transaction = [
                TransactionProduct(
                    quantity = product.quantity,
                    product_id = product.product_id
                ) 
                for product in checked_products
            ]
            transaction_create.products_transaction = products_transaction
            transaction = transaction_create.insert(db)

            # Increments products stock
            self._update_products_inventory(db, products_to_update, checked_products)


        elif transaction.type == TransactionTypeEnum.outgoing:
            checked_products = self._sort_by_id_check_and_sum_duplicates(transaction.products)
            products_ids = self._check_if_products_payload_is_greater_than_zero(checked_products)

            # Get products inventory
            products_to_update = self._get_products_from_database(db, products_ids)
            
            # Check if stock has enough quantity to outgoing
            self._check_if_stock_has_enough_outgoing_quantity(products_to_update, checked_products)

            # Creates the record of the current transaction
            transaction_create = Transaction(
                **transaction.dict(exclude_unset=True, exclude={'products', 'provider_id'})
            )
            transaction_create.created_by = user.id

            # Creates product transactions records
            products_transaction = [
                TransactionProduct(
                    quantity = product.quantity,
                    product_id = product.product_id
                ) 
                for product in checked_products
            ]
            transaction_create.products_transaction = products_transaction
            transaction = transaction_create.insert(db)

            # Decrements products stock
            self._update_products_inventory_outgoing(db, products_to_update, checked_products)


        # transaction = self.fetch_one(db, transaction.id)
        return TransactionResponse.from_orm(transaction)

    def make_response(self, db: Session, err: str):
        products_ids: List[int] = eval(err)
        products = db.query(Product).filter(Product.id.in_(products_ids)).all()
        
        data = []
        for product in products:
            data.append({
                "id": product.id,
                "name": product.name,
                "inventory": product.inventory
            })
        
        return data