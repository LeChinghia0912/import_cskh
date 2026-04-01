<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class CskhStatus extends Model
{
    protected $connection = 'mysql4';

    protected $table = 'cskh_status';

    protected $fillable = [
        'code',
        'description',
        'kanban_stage',
        'is_active',
    ];

    protected $casts = [
        'is_active' => 'boolean',
        'kanban_stage' => 'integer',
    ];
}

