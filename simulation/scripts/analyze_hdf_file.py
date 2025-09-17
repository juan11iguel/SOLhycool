#!/usr/bin/env python3
"""
HDF5 File Space Analysis Tool

This script analyzes HDF5 files to identify which datasets, groups, and attributes
are taking the most storage space. It provides detailed statistics about file
structure and helps optimize storage usage.

Features:
- Recursive analysis of all groups and datasets
- Size calculation for datasets, attributes, and metadata
- Sorting by size to identify largest elements
- Detailed type and compression information
- Human-readable size formatting
- Optional depth limiting for large files

Usage:
    python analyze_hdf_file.py <hdf5_file> [options]
    
Example:
    python analyze_hdf_file.py data.h5 --top 20 --min-size 1MB
    python analyze_hdf_file.py results.h5 --show-attributes --max-depth 3

Author: SOLhycool Team
Created: September 2025
"""

import argparse
import h5py
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys


def format_bytes(size_bytes: int) -> str:
    """Convert bytes to human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def get_dataset_info(dataset: h5py.Dataset) -> Dict[str, Any]:
    """Extract detailed information about a dataset."""
    info = {
        'type': 'dataset',
        'dtype': str(dataset.dtype),
        'shape': dataset.shape,
        'size_bytes': dataset.nbytes,
        'chunks': dataset.chunks,
        'compression': dataset.compression,
        'compression_opts': dataset.compression_opts,
        'shuffle': dataset.shuffle,
        'fletcher32': dataset.fletcher32,
        'scaleoffset': dataset.scaleoffset,
        'fillvalue': dataset.fillvalue,
        'maxshape': dataset.maxshape,
    }
    
    # Calculate storage efficiency
    if dataset.chunks and dataset.compression:
        # For chunked, compressed datasets, get actual storage size
        try:
            storage_size = dataset.id.get_storage_size()
            if storage_size > 0:
                info['storage_bytes'] = storage_size
                info['compression_ratio'] = info['size_bytes'] / storage_size
            else:
                info['storage_bytes'] = info['size_bytes']
                info['compression_ratio'] = 1.0
        except Exception:
            info['storage_bytes'] = info['size_bytes']
            info['compression_ratio'] = 1.0
    else:
        info['storage_bytes'] = info['size_bytes']
        info['compression_ratio'] = 1.0
    
    return info


def get_group_info(group: h5py.Group) -> Dict[str, Any]:
    """Extract information about a group."""
    return {
        'type': 'group',
        'num_items': len(group),
        'size_bytes': 0,  # Will be calculated recursively
        'storage_bytes': 0,
    }


def get_attribute_info(obj: h5py.HLObject) -> Dict[str, Any]:
    """Calculate total size of all attributes for an object."""
    total_size = 0
    attr_details = {}
    
    for attr_name in obj.attrs:
        attr_value = obj.attrs[attr_name]
        if hasattr(attr_value, 'nbytes'):
            attr_size = attr_value.nbytes
        elif isinstance(attr_value, (str, bytes)):
            attr_size = len(str(attr_value).encode('utf-8'))
        elif isinstance(attr_value, (int, float)):
            attr_size = 8  # Approximate
        else:
            attr_size = sys.getsizeof(attr_value)
        
        total_size += attr_size
        attr_details[attr_name] = {
            'size_bytes': attr_size,
            'dtype': type(attr_value).__name__,
            'value': str(attr_value)[:100] + ('...' if len(str(attr_value)) > 100 else '')
        }
    
    return {
        'total_size': total_size,
        'count': len(obj.attrs),
        'details': attr_details
    }


def analyze_hdf5_recursive(
    obj: h5py.HLObject, 
    path: str = "/",
    max_depth: Optional[int] = None,
    current_depth: int = 0,
    show_attributes: bool = False
) -> List[Dict[str, Any]]:
    """Recursively analyze HDF5 file structure."""
    results = []
    
    if max_depth is not None and current_depth > max_depth:
        return results
    
    # Analyze current object
    if isinstance(obj, h5py.Dataset):
        info = get_dataset_info(obj)
        info['path'] = path
        info['depth'] = current_depth
        
        if show_attributes:
            info['attributes'] = get_attribute_info(obj)
        
        results.append(info)
        
    elif isinstance(obj, h5py.Group):
        info = get_group_info(obj)
        info['path'] = path
        info['depth'] = current_depth
        
        if show_attributes:
            info['attributes'] = get_attribute_info(obj)
        
        # Recursively analyze group contents
        child_results = []
        for key in obj.keys():
            child_path = f"{path.rstrip('/')}/{key}" if path != "/" else f"/{key}"
            child_results.extend(
                analyze_hdf5_recursive(
                    obj[key], 
                    child_path, 
                    max_depth, 
                    current_depth + 1,
                    show_attributes
                )
            )
        
        # Calculate total size from children
        total_size = sum(child['size_bytes'] for child in child_results if 'size_bytes' in child)
        total_storage = sum(child['storage_bytes'] for child in child_results if 'storage_bytes' in child)
        
        info['size_bytes'] = total_size
        info['storage_bytes'] = total_storage
        info['children'] = child_results
        
        results.append(info)
        results.extend(child_results)
    
    return results


def filter_results(
    results: List[Dict[str, Any]], 
    min_size_bytes: int = 0,
    object_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Filter results based on size and type criteria."""
    filtered = []
    
    for item in results:
        # Size filter
        size_to_check = item.get('storage_bytes', item.get('size_bytes', 0))
        if size_to_check < min_size_bytes:
            continue
        
        # Type filter
        if object_types and item.get('type') not in object_types:
            continue
        
        filtered.append(item)
    
    return filtered


def create_summary_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a summary report of the analysis."""
    datasets = [r for r in results if r.get('type') == 'dataset']
    groups = [r for r in results if r.get('type') == 'group']
    
    total_size = sum(r.get('size_bytes', 0) for r in results)
    total_storage = sum(r.get('storage_bytes', 0) for r in results)
    
    return {
        'total_objects': len(results),
        'total_datasets': len(datasets),
        'total_groups': len(groups),
        'total_logical_size': total_size,
        'total_storage_size': total_storage,
        'overall_compression_ratio': total_size / total_storage if total_storage > 0 else 1.0,
        'largest_dataset': max(datasets, key=lambda x: x.get('storage_bytes', 0)) if datasets else None,
        'compression_stats': {
            'compressed_datasets': len([d for d in datasets if d.get('compression')]),
            'avg_compression_ratio': np.mean([d.get('compression_ratio', 1.0) for d in datasets]) if datasets else 1.0,
            'best_compression': max([d.get('compression_ratio', 1.0) for d in datasets]) if datasets else 1.0,
        }
    }


def print_results(
    results: List[Dict[str, Any]], 
    summary: Dict[str, Any],
    top_n: int = 10,
    show_attributes: bool = False
):
    """Print formatted analysis results."""
    
    print("=" * 70)
    print("HDF5 SPACE ANALYSIS")
    print("=" * 70)
    
    # Key summary metrics only
    print(f"File contains: {summary['total_datasets']} datasets, {summary['total_groups']} groups")
    print(f"Total size: {format_bytes(summary['total_storage_size'])}")
    
    if summary['compression_stats']['compressed_datasets'] > 0:
        print(f"Compression: {summary['compression_stats']['avg_compression_ratio']:.1f}x average ratio")
    
    # Sort by storage size (descending) and show only the biggest ones
    sorted_results = sorted(results, key=lambda x: x.get('storage_bytes', 0), reverse=True)
    
    print(f"\n🔍 TOP {min(top_n, len(sorted_results))} LARGEST OBJECTS")
    print("-" * 70)
    
    for i, item in enumerate(sorted_results[:top_n]):
        size_str = format_bytes(item.get('storage_bytes', 0))
        percentage = (item.get('storage_bytes', 0) / summary['total_storage_size']) * 100
        
        print(f"{i+1:2d}. {size_str:>10} ({percentage:4.1f}%) {item['path']}")
        
        # Show key details only for the largest items
        if i < 5:  # Only for top 5
            if item['type'] == 'dataset':
                shape_str = f"{item.get('shape', '')}"
                dtype_str = item.get('dtype', '')
                print(f"     └─ Dataset: {shape_str} {dtype_str}")
                
                if item.get('compression'):
                    ratio = item.get('compression_ratio', 1.0)
                    print(f"     └─ Compressed {item['compression']} ({ratio:.1f}x)")
            
            elif item['type'] == 'group':
                print(f"     └─ Group with {item.get('num_items', 0)} items")
    
    # Show space distribution
    datasets = [r for r in results if r.get('type') == 'dataset']
    if datasets:
        top_5_size = sum(r.get('storage_bytes', 0) for r in sorted_results[:5])
        top_5_percentage = (top_5_size / summary['total_storage_size']) * 100
        print(f"\nTop 5 objects account for {top_5_percentage:.1f}% of total size")


def main():
    """Main function to run the HDF5 analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze HDF5 files to find what's taking the most space",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s data.h5                    # Quick analysis
  %(prog)s results.h5 --top 20        # Show top 20 largest
  %(prog)s file.h5 --min-size 1MB     # Only show items > 1MB
  %(prog)s file.h5 --csv report.csv   # Export detailed report
        """
    )
    
    parser.add_argument('file', help='Path to HDF5 file to analyze')
    parser.add_argument('--top', type=int, default=15, 
                       help='Number of largest objects to show (default: 15)')
    parser.add_argument('--min-size', type=str, default='0B',
                       help='Minimum size to include (e.g., 1MB, 500KB)')
    parser.add_argument('--csv', type=str, metavar='FILE',
                       help='Export detailed results to CSV file')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed information (attributes, compression details)')
    
    args = parser.parse_args()
    
    # Validate file path
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ Error: File '{args.file}' not found")
        sys.exit(1)
    
    # Parse minimum size
    try:
        min_size_bytes = parse_size(args.min_size)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    
    print(f"📁 Analyzing: {file_path.name}")
    print(f"📏 File size: {format_bytes(file_path.stat().st_size)}")
    
    try:
        with h5py.File(file_path, 'r') as f:
            # Perform analysis
            results = analyze_hdf5_recursive(f, show_attributes=args.verbose)
            
            # Filter results
            filtered_results = filter_results(results, min_size_bytes=min_size_bytes)
            
            # Create summary
            summary = create_summary_report(filtered_results)
            
            # Print results
            print_results(filtered_results, summary, top_n=args.top, show_attributes=args.verbose)
            
            # Export to CSV if requested
            if args.csv:
                export_to_csv(filtered_results, args.csv)
                print(f"\n📄 Detailed report exported to: {args.csv}")
    
    except Exception as e:
        print(f"❌ Error analyzing file: {e}")
        sys.exit(1)


def parse_size(size_str: str) -> int:
    """Parse human-readable size string to bytes."""
    size_str = size_str.upper().strip()
    
    multipliers = {
        'B': 1,
        'KB': 1024,
        'MB': 1024**2,
        'GB': 1024**3,
        'TB': 1024**4,
    }
    
    for suffix, multiplier in multipliers.items():
        if size_str.endswith(suffix):
            number_part = size_str[:-len(suffix)].strip()
            try:
                return int(float(number_part) * multiplier)
            except ValueError:
                raise ValueError(f"Invalid size format: {size_str}")
    
    # If no suffix, assume bytes
    try:
        return int(size_str)
    except ValueError:
        raise ValueError(f"Invalid size format: {size_str}")


def export_to_csv(results: List[Dict[str, Any]], output_path: str):
    """Export analysis results to CSV file."""
    rows = []
    
    for item in results:
        row = {
            'path': item['path'],
            'type': item['type'],
            'storage_size_bytes': item.get('storage_bytes', 0),
            'logical_size_bytes': item.get('size_bytes', 0),
            'storage_size_human': format_bytes(item.get('storage_bytes', 0)),
            'logical_size_human': format_bytes(item.get('size_bytes', 0)),
            'compression_ratio': item.get('compression_ratio', 1.0),
            'depth': item.get('depth', 0),
        }
        
        if item['type'] == 'dataset':
            row.update({
                'dtype': item.get('dtype', ''),
                'shape': str(item.get('shape', '')),
                'compression': item.get('compression', ''),
                'chunks': str(item.get('chunks', '')),
            })
        elif item['type'] == 'group':
            row.update({
                'num_items': item.get('num_items', 0),
                'dtype': '',
                'shape': '',
                'compression': '',
                'chunks': '',
            })
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df = df.sort_values('storage_size_bytes', ascending=False)
    df.to_csv(output_path, index=False)





if __name__ == "__main__":
    main()