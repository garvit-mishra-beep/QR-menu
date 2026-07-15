from datetime import datetime, date, time
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.models import RestaurantSetting, Table, Category, MenuItem, Order, OrderItem, OrderStatus
from app.schemas import (
    CategoryCreate, CategoryUpdate, MenuItemCreate, MenuItemUpdate,
    OrderCreate, RestaurantSettingUpdate
)

# ==========================================
# Restaurant Settings CRUD
# ==========================================
def get_restaurant_settings(db: Session) -> RestaurantSetting:
    """
    Get the single restaurant settings record. If none exists, create default.
    """
    setting = db.query(RestaurantSetting).first()
    if not setting:
        setting = RestaurantSetting(
            restaurant_name="Sai Kripa Restaurant",
            address="",
            phone="",
            opening_time="11:00 AM",
            closing_time="11:00 PM",
            logo_url="",
            currency="INR",
            gst_percentage=5.0
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting

def update_restaurant_settings(db: Session, db_settings: RestaurantSetting, updates: RestaurantSettingUpdate) -> RestaurantSetting:
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_settings, key, value)
    db.commit()
    db.refresh(db_settings)
    return db_settings


# ==========================================
# Table CRUD
# ==========================================
def get_tables(db: Session) -> List[Table]:
    return db.query(Table).filter(Table.is_active == True).all()

def get_table_by_number(db: Session, table_number: int) -> Optional[Table]:
    return db.query(Table).filter(Table.table_number == table_number, Table.is_active == True).first()

def get_table_by_id(db: Session, table_id: int) -> Optional[Table]:
    return db.query(Table).filter(Table.id == table_id, Table.is_active == True).first()


# ==========================================
# Category CRUD
# ==========================================
def get_categories(db: Session) -> List[Category]:
    return db.query(Category).order_by(Category.display_order.asc(), Category.name.asc()).all()

def get_category_by_id(db: Session, category_id: int) -> Optional[Category]:
    return db.query(Category).filter(Category.id == category_id).first()

def get_category_by_name(db: Session, name: str) -> Optional[Category]:
    return db.query(Category).filter(Category.name == name).first()

def create_category(db: Session, category: CategoryCreate) -> Category:
    db_category = Category(
        name=category.name,
        display_order=category.display_order
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def update_category(db: Session, db_category: Category, updates: CategoryUpdate) -> Category:
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)
    db.commit()
    db.refresh(db_category)
    return db_category

def delete_category(db: Session, db_category: Category) -> None:
    db.delete(db_category)
    db.commit()


# ==========================================
# Menu Item CRUD
# ==========================================
def get_menu_items(
    db: Session,
    category: Optional[str] = None,
    search: Optional[str] = None,
    available: Optional[bool] = None
) -> List[MenuItem]:
    query = db.query(MenuItem).join(Category)
    
    if category:
        query = query.filter(Category.name.ilike(category))
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (MenuItem.name.ilike(search_filter)) | 
            (MenuItem.description.ilike(search_filter))
        )
    if available is not None:
        query = query.filter(MenuItem.is_available == available)
        
    return query.order_by(MenuItem.display_order.asc(), MenuItem.name.asc()).all()

def get_menu_item(db: Session, item_id: int) -> Optional[MenuItem]:
    return db.query(MenuItem).filter(MenuItem.id == item_id).first()

def create_menu_item(db: Session, item: MenuItemCreate) -> MenuItem:
    db_item = MenuItem(
        category_id=item.category_id,
        name=item.name,
        description=item.description,
        price=item.price,
        image_url=item.image_url,
        is_available=item.is_available,
        is_best_seller=item.is_best_seller,
        is_chef_special=item.is_chef_special,
        display_order=item.display_order
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_menu_item(db: Session, db_item: MenuItem, updates: MenuItemUpdate) -> MenuItem:
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)
    db.commit()
    db.refresh(db_item)
    return db_item

def delete_menu_item(db: Session, db_item: MenuItem) -> None:
    db.delete(db_item)
    db.commit()


# ==========================================
# Orders CRUD & Business Logic
# ==========================================
def get_order(db: Session, order_id: int) -> Optional[Order]:
    return (
        db.query(Order)
        .options(joinedload(Order.table), joinedload(Order.items).joinedload(OrderItem.menu_item))
        .filter(Order.id == order_id)
        .first()
    )

def get_orders(
    db: Session,
    status: Optional[OrderStatus] = None,
    table_number: Optional[int] = None,
    today: Optional[bool] = None
) -> List[Order]:
    query = (
        db.query(Order)
        .join(Table)
        .options(joinedload(Order.table), joinedload(Order.items).joinedload(OrderItem.menu_item))
    )
    
    if status:
        query = query.filter(Order.status == status)
    if table_number:
        query = query.filter(Table.table_number == table_number)
    if today:
        start_of_day = datetime.combine(date.today(), time.min)
        end_of_day = datetime.combine(date.today(), time.max)
        query = query.filter(Order.created_at >= start_of_day, Order.created_at <= end_of_day)
        
    return query.order_by(Order.created_at.desc()).all()

def create_order(db: Session, order_data: OrderCreate, table: Table) -> Order:
    # Get settings to find GST percentage
    settings = get_restaurant_settings(db)
    
    # Pre-fetch all menu items to minimize queries and validate
    menu_item_ids = [item.menu_item_id for item in order_data.items]
    menu_items = db.query(MenuItem).filter(MenuItem.id.in_(menu_item_ids)).all()
    menu_item_map = {item.id: item for item in menu_items}
    
    # Validate items exist and are available
    for order_item in order_data.items:
        menu_item = menu_item_map.get(order_item.menu_item_id)
        if not menu_item:
            raise ValueError(f"Menu item with ID {order_item.menu_item_id} does not exist.")
        if not menu_item.is_available:
            raise ValueError(f"Menu item '{menu_item.name}' is currently out of stock / unavailable.")
            
    # Calculate subtotal using actual database prices (ignoring frontend inputs)
    subtotal = 0.0
    order_items_to_create = []
    
    # 1. Create temporary Order object so we get an ID
    db_order = Order(
        table_id=table.id,
        status=OrderStatus.PENDING,
        total_amount=0.0
    )
    db.add(db_order)
    db.flush()  # Allocate ID
    
    # 2. Add OrderItems and calculate totals
    for order_item in order_data.items:
        menu_item = menu_item_map[order_item.menu_item_id]
        item_price = menu_item.price
        subtotal += item_price * order_item.quantity
        
        db_order_item = OrderItem(
            order_id=db_order.id,
            menu_item_id=order_item.menu_item_id,
            quantity=order_item.quantity,
            price=item_price,
            special_instruction=order_item.special_instruction
        )
        db.add(db_order_item)
        order_items_to_create.append(db_order_item)
        
    # Calculate final total including GST
    gst_amount = subtotal * (settings.gst_percentage / 100.0)
    total_amount = round(subtotal + gst_amount, 2)
    
    db_order.total_amount = total_amount
    db.commit()
    
    # Re-fetch with eager loading so relationships are populated for the response
    return get_order(db, db_order.id)

def validate_and_update_order_status(db: Session, db_order: Order, new_status: OrderStatus) -> Order:
    """
    Validate that the status transition is allowed:
    Pending -> Preparing -> Ready -> Served
    """
    current_status = db_order.status
    
    if current_status == new_status:
        return db_order
        
    # Define valid transitions
    valid_transitions = {
        OrderStatus.PENDING: [OrderStatus.PREPARING],
        OrderStatus.PREPARING: [OrderStatus.READY],
        OrderStatus.READY: [OrderStatus.SERVED],
        OrderStatus.SERVED: []  # Final state, no transitions allowed
    }
    
    allowed = valid_transitions.get(current_status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition from '{current_status.value}' to '{new_status.value}'. "
            f"Allowed next status is: {[s.value for s in allowed]}"
        )
        
    db_order.status = new_status
    db.commit()
    db.refresh(db_order)
    return db_order


# ==========================================
# Manager Dashboard
# ==========================================
def get_dashboard_stats(db: Session) -> dict:
    start_of_day = datetime.combine(date.today(), time.min)
    end_of_day = datetime.combine(date.today(), time.max)
    
    # 1. Total menu items
    menu_items_count = db.query(func.count(MenuItem.id)).scalar() or 0
    
    # 2. Total categories
    categories_count = db.query(func.count(Category.id)).scalar() or 0
    
    # 3. Orders today
    orders_today_count = db.query(func.count(Order.id)).filter(
        Order.created_at >= start_of_day,
        Order.created_at <= end_of_day
    ).scalar() or 0
    
    # 4. Status breakdown today
    pending_count = db.query(func.count(Order.id)).filter(Order.status == OrderStatus.PENDING).scalar() or 0
    preparing_count = db.query(func.count(Order.id)).filter(Order.status == OrderStatus.PREPARING).scalar() or 0
    ready_count = db.query(func.count(Order.id)).filter(Order.status == OrderStatus.READY).scalar() or 0
    
    # Served today
    served_today_count = db.query(func.count(Order.id)).filter(
        Order.status == OrderStatus.SERVED,
        Order.created_at >= start_of_day,
        Order.created_at <= end_of_day
    ).scalar() or 0
    
    return {
        "orders_today": orders_today_count,
        "pending": pending_count,
        "preparing": preparing_count,
        "ready": ready_count,
        "served": served_today_count,
        "menu_items": menu_items_count,
        "categories": categories_count
    }
