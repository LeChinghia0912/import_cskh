<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class CskhReceivingDepartment extends Model
{
    protected $connection = 'mysql4';

    protected $table = 'cskh_receiving_departments';

    protected $fillable = [
        'description',
        'is_active',
    ];

    protected $casts = [
        'is_active' => 'boolean',
    ];
}

