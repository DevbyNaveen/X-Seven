"""Safe Supabase query helpers."""
from fastapi import HTTPException
import logging


async def safe_supabase_select(supabase, table_name: str, select_fields: str = "*", filter_field: str = None, filter_value=None):
    """Safely select data from Supabase with error handling."""
    try:
        query = supabase.table(table_name).select(select_fields)
        
        if filter_field and filter_value is not None:
            query = query.eq(filter_field, filter_value)
            
        response = query.execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404, 
                detail=f"No {table_name} found"
            )
            
        return response.data
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logging.error(f"Database error in {table_name}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Database operation failed: {str(e)}"
        )


async def safe_supabase_insert(supabase, table_name: str, data: dict):
    """Safely insert data into Supabase."""
    try:
        response = supabase.table(table_name).insert(data).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create {table_name}"
            )
            
        return response.data[0]
        
    except Exception as e:
        logging.error(f"Insert error in {table_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create {table_name}: {str(e)}"
        )


async def safe_supabase_update(supabase, table_name: str, data: dict, filter_field: str, filter_value):
    """Safely update data in Supabase."""
    try:
        response = supabase.table(table_name).update(data).eq(filter_field, filter_value).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail=f"No {table_name} found to update"
            )
            
        return response.data[0]
        
    except Exception as e:
        logging.error(f"Update error in {table_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update {table_name}: {str(e)}"
        )


async def safe_supabase_delete(supabase, table_name: str, filter_field: str, filter_value):
    """Safely delete data from Supabase."""
    try:
        response = supabase.table(table_name).delete().eq(filter_field, filter_value).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail=f"No {table_name} found to delete"
            )
            
        return response.data[0]
        
    except Exception as e:
        logging.error(f"Delete error in {table_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete {table_name}: {str(e)}"
        )
