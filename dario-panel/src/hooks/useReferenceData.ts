import { useQuery } from '@tanstack/react-query';
import { catalogApi } from '../api/catalog';
import type { Location } from '../api/types';
import { usersApi } from '../api/users';
import { warehouseApi } from '../api/warehouse';

export function useUsers(enabled = true) {
  return useQuery({ queryKey: ['users'], queryFn: () => usersApi.list(), enabled });
}

export function useProducts(enabled = true) {
  return useQuery({ queryKey: ['catalog', 'products'], queryFn: catalogApi.products, enabled });
}

export function useVariants(enabled = true) {
  return useQuery({ queryKey: ['catalog', 'variants'], queryFn: () => catalogApi.variants(), enabled });
}

export function useCategories(enabled = true) {
  return useQuery({ queryKey: ['catalog', 'categories'], queryFn: () => catalogApi.categories(false), enabled });
}

export function useWarehouses(enabled = true) {
  return useQuery({ queryKey: ['warehouses'], queryFn: warehouseApi.list, enabled });
}

export function useAllLocations(enabled = true) {
  return useQuery({
    queryKey: ['warehouses', 'all-locations'],
    enabled,
    queryFn: async () => {
      const warehouses = await warehouseApi.list();
      const groups = await Promise.all(
        warehouses.map(async (warehouse) => ({
          warehouse,
          locations: await warehouseApi.locations(warehouse.id),
        })),
      );
      return groups.flatMap(({ warehouse, locations }) =>
        locations.map((location): Location & { warehouse_name: string; warehouse_code: string } => ({
          ...location,
          warehouse_name: warehouse.name,
          warehouse_code: warehouse.code,
        })),
      );
    },
  });
}
